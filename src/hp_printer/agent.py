import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Request, Response

from . import __version__
from .auth import AuthError, refresh_tokens
from .config import CUPS_UUID, LAN_URL, LOCAL_PORT, PRINTER_PATH, PUBLIC_URL
from .credentials import app_dir, load_tokens, save_tokens
from .ipp import (
    CREATE_OPERATIONS,
    IPPError,
    parse,
    prepare_request,
    request,
    response_error,
    rewrite_response,
)

log = logging.getLogger("hp_printer.agent")


class Credentials:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def access_token(self):
        async with self.lock:
            try:
                tokens = load_tokens()
                # Only used to schedule refresh; gateway verifies the actual signature and policy.
                expiration = jwt.decode(tokens["access_token"], options={"verify_signature": False})["exp"]
                if expiration < time.time() + 45:
                    tokens = await asyncio.to_thread(refresh_tokens, tokens)
                    save_tokens(tokens)
                return tokens["access_token"]
            except (OSError, KeyError, ValueError, jwt.PyJWTError, AuthError, httpx.HTTPError) as exc:
                raise AuthError("请重新运行安装包登录 ICTHub。") from exc


class Routing:
    def __init__(self, directory: Path):
        self.directory = directory
        self.lan_available = False
        self.probed_at = 0.0
        self.lock = asyncio.Lock()
        try:
            self.pins = json.loads((directory / "routes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.pins = {}

    def remote_only(self):
        try:
            return json.loads((self.directory / "settings.json").read_text(encoding="utf-8")).get("remote_only", False) is True
        except (OSError, ValueError):
            return False

    async def route(self, client: httpx.AsyncClient, job_id: int | None):
        if job_id and str(job_id) in self.pins:
            return self.pins[str(job_id)]
        if self.remote_only():
            return "remote"
        async with self.lock:
            if time.monotonic() - self.probed_at > 10:
                try:
                    response = await client.post(
                        LAN_URL, content=request().encode(), headers={"Content-Type": "application/ipp"}, timeout=2,
                    )
                    info = parse(response.content, allow_document=False)
                    self.lan_available = response.status_code == 200 and info.code < 0x400 and info.values(b"printer-uuid") == [CUPS_UUID.encode()]
                except (httpx.HTTPError, IPPError):
                    self.lan_available = False
                self.probed_at = time.monotonic()
        return "lan" if self.lan_available else "remote"

    def pin(self, job_id: int, route: str):
        self.pins[str(job_id)] = route
        self.pins = dict(list(self.pins.items())[-1000:])
        temporary = self.directory / "routes.tmp"
        temporary.write_text(json.dumps(self.pins), encoding="utf-8")
        os.replace(temporary, self.directory / "routes.json")


def create_agent(directory: Path | None = None):
    directory = directory or app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    routing = Routing(directory)
    credentials = Credentials()
    semaphore = asyncio.Semaphore(2)
    status = {"route": "unknown", "loginRequired": False}

    @asynccontextmanager
    async def lifespan(app):
        app.state.http = httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(180, connect=10), follow_redirects=False)
        yield
        await app.state.http.aclose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def localhost_only(req: Request, call_next):
        if (
            req.client.host not in ("127.0.0.1", "::1")
            or req.headers.get("host") not in (f"127.0.0.1:{LOCAL_PORT}", f"localhost:{LOCAL_PORT}")
            or "origin" in req.headers
        ):
            return Response(status_code=403)
        return await call_next(req)

    @app.get("/health")
    def health():
        return {"service": "icthub-printer-agent", "version": __version__, **status}

    @app.get(PRINTER_PATH)
    @app.get(PRINTER_PATH.lower())
    def info():
        return Response("ICTHub Windows IPP bridge", media_type="text/plain")

    @app.post(PRINTER_PATH)
    @app.post(PRINTER_PATH.lower())
    async def forward(req: Request):
        if req.headers.get("content-type", "").split(";")[0].strip().lower() != "application/ipp":
            raise HTTPException(415, "IPP request required")
        async with semaphore:
            body = bytearray()
            async for chunk in req.stream():
                if len(body) + len(chunk) > 80 * 1024 * 1024:
                    raise HTTPException(413, "Maximum print request is 80 MiB")
                body.extend(chunk)
            try:
                incoming = parse(bytes(body))
                prepare_request(incoming, "localhost:631")
                job_id = incoming.job_id()
            except IPPError as exc:
                raise HTTPException(400, str(exc)) from None
            route = await routing.route(req.app.state.http, job_id)
            status["route"] = route
            headers = {"Content-Type": "application/ipp"}
            if route == "remote":
                try:
                    headers["Authorization"] = "Bearer " + await credentials.access_token()
                    status["loginRequired"] = False
                except AuthError:
                    status["loginRequired"] = True
                    return Response(response_error(incoming, 0x0403, "Run ICTHub Printer to sign in again"), media_type="application/ipp")
            target = LAN_URL if route == "lan" else PUBLIC_URL + "/ipp/print"
            try:
                response = await req.app.state.http.post(target, content=incoming.encode(), headers=headers)
                if response.status_code == 401:
                    status["loginRequired"] = True
                    return Response(response_error(incoming, 0x0403, "ICTHub authorization expired"), media_type="application/ipp")
                if response.status_code != 200:
                    raise httpx.HTTPError("Upstream rejected request")
                outgoing = parse(response.content, allow_document=False)
            except (httpx.HTTPError, IPPError):
                log.warning("Request outcome uncertain route=%s operation=%s", route, incoming.code)
                return Response(response_error(incoming, 0x0500, "Print result unknown; inspect queue before retrying"), media_type="application/ipp")
            if outgoing.code < 0x400 and incoming.code in CREATE_OPERATIONS:
                new_id = outgoing.job_id()
                if new_id:
                    routing.pin(new_id, route)
                    log.info("accepted job=%s route=%s", new_id, route)
            rewrite_response(outgoing, f"127.0.0.1:{LOCAL_PORT}")
            return Response(outgoing.encode(), media_type="application/ipp")

    return app
