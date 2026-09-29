import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

from . import __version__
from .auth import AuthError, TokenVerifier, owner_key
from .config import GatewayConfig
from .ipp import (
    CREATE_OPERATIONS,
    JOB_OPERATIONS,
    IPPError,
    Message,
    parse,
    prepare_request,
    response_error,
)

log = logging.getLogger("hp_printer.gateway")


class JobOwners:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, owner TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def record(self, job_id: int, owner: str):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO jobs (id, owner) VALUES (?, ?)", (job_id, owner))

    def owns(self, job_id: int, owner: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone() is not None


def create_app(config: GatewayConfig | None = None, *, verifier=None, transport=None) -> FastAPI:
    config = config or GatewayConfig()
    state_dir = Path(config.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    owners = JobOwners(state_dir / "jobs.db")
    verifier = verifier or TokenVerifier(config.issuer, config.client_id, config.required_group)
    concurrency = asyncio.Semaphore(4)

    @asynccontextmanager
    async def lifespan(app):
        app.state.http = httpx.AsyncClient(
            trust_env=False, transport=transport,
            timeout=httpx.Timeout(180, connect=5), follow_redirects=False,
        )
        yield
        await app.state.http.aclose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    def identity(req: Request):
        header = req.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(401, "Authentik login required", headers={"WWW-Authenticate": "Bearer"})
        try:
            return verifier.verify(header[7:])
        except AuthError as exc:
            raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from None

    @app.get("/health")
    def health():
        return {"service": "hp-printer", "version": __version__, "revision": os.getenv("HP_PRINTER_REVISION", "unknown")}

    @app.get("/")
    def index():
        return Response("ICTHub 打印服务已启动。请运行 Windows 安装包登录并添加打印机。", media_type="text/plain")

    @app.get("/v1/me")
    def me(req: Request):
        claims = identity(req)
        return {"authorized": True, "username": claims.get("preferred_username", ""), "emailVerified": True}

    @app.post("/ipp/print")
    async def print_request(req: Request):
        # Validate credentials before reading potentially large print documents.
        claims = await asyncio.to_thread(identity, req)
        owner = owner_key(claims)
        if req.headers.get("content-type", "").split(";")[0].strip().lower() != "application/ipp":
            raise HTTPException(415, "IPP data required")
        if concurrency.locked():
            raise HTTPException(503, "Printer gateway busy; the request was not submitted")
        async with concurrency:
            data = bytearray()
            try:
                async with asyncio.timeout(120):
                    async for chunk in req.stream():
                        if len(data) + len(chunk) > config.max_request_bytes:
                            raise HTTPException(413, "Print request exceeds 80 MiB")
                        data.extend(chunk)
            except TimeoutError:
                raise HTTPException(408, "Upload timed out before submission") from None
            try:
                incoming = parse(bytes(data))
            except IPPError as exc:
                raise HTTPException(400, str(exc)) from None
            try:
                prepare_request(incoming, "localhost:631", owner=owner)
                job_id = incoming.job_id()
                if incoming.code in JOB_OPERATIONS and not owners.owns(job_id, owner):
                    return Response(response_error(incoming, 0x0406, "Job not found"), media_type="application/ipp")
            except IPPError as exc:
                return Response(response_error(incoming, 0x0400, str(exc)), media_type="application/ipp")
            try:
                # A failed or ambiguous POST is never retried by this gateway.
                result = await req.app.state.http.post(
                    config.cups_url, content=incoming.encode(),
                    headers={"Content-Type": "application/ipp"},
                )
                if result.status_code != 200:
                    raise HTTPException(502, "CUPS did not confirm the request; check the queue before retrying")
                outgoing = parse(result.content, allow_document=False)
            except (httpx.HTTPError, IPPError):
                log.warning("CUPS response uncertain operation=%s owner=%s", incoming.code, owner)
                raise HTTPException(502, "Print result is unknown; check the queue before retrying") from None
            if outgoing.code < 0x0400 and incoming.code in CREATE_OPERATIONS:
                new_id = outgoing.job_id()
                if new_id:
                    owners.record(new_id, owner)
                    log.info("accepted job=%s owner=%s", new_id, owner)
            if incoming.code == 0x000A:
                kept = []
                for group in outgoing.groups:
                    if group.tag != 2:
                        kept.append(group)
                        continue
                    job = Message(outgoing.version, outgoing.code, outgoing.request_id, [group]).job_id()
                    if job and owners.owns(job, owner):
                        kept.append(group)
                outgoing.groups = kept
            return Response(outgoing.encode(), media_type="application/ipp", headers={"Cache-Control": "no-store"})

    return app
