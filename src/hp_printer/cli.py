from pathlib import Path

import httpx
import typer
import uvicorn

from . import __version__
from .config import PRINTER_PATH, GatewayConfig
from .ipp import parse, request

app = typer.Typer(help="ICTHub printer gateway and read-only diagnostics.")


@app.callback()
def main(version: bool = typer.Option(False, "--version", is_eager=True)):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def serve(config: Path | None = typer.Option(None, "--config")):
    from .gateway import create_app

    settings = GatewayConfig.load(config)
    uvicorn.run(create_app(settings), host=settings.listen, port=settings.port, access_log=False, proxy_headers=False)


@app.command()
def doctor():
    """Read the existing local CUPS queue; never submit a document."""
    import json

    result = httpx.post(
        "http://127.0.0.1:631" + PRINTER_PATH, content=request().encode(),
        headers={"Content-Type": "application/ipp"}, timeout=10, trust_env=False,
    )
    result.raise_for_status()
    message = parse(result.content, allow_document=False)
    typer.echo(json.dumps({"version": __version__, "ippStatus": message.code,
                          "printerName": [v.decode(errors="replace") for v in message.values(b"printer-name")],
                          "stateReasons": [v.decode(errors="replace") for v in message.values(b"printer-state-reasons")]}, ensure_ascii=False))
