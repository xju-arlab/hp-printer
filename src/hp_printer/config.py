import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

QUEUE = "HP_DeskJet_4900"
PRINTER_NAME = "算法实验室·惠普打印机"
ISSUER = "https://auth.icthub.top/application/o/hp-printer/"
CLIENT_ID = "icthub-hp-printer-windows"
REQUIRED_GROUP = "hp-printer-users"
PUBLIC_URL = "https://hp.icthub.top"
LOCAL_PORT = 18765
CALLBACK_PORT = 18766
PRINTER_PATH = f"/printers/{QUEUE}"
LOCAL_URL = f"http://127.0.0.1:{LOCAL_PORT}{PRINTER_PATH}"
LAN_URL = f"http://192.168.5.87:631{PRINTER_PATH}"
PRINTER_UUID = "urn:uuid:36b6d66a-e081-5874-bd1a-cf8d00edc991"
CUPS_UUID = "urn:uuid:67cd2fe6-5447-3ddb-6acb-756a0120186b"


@dataclass(frozen=True)
class GatewayConfig:
    listen: str = "127.0.0.1"
    port: int = 8765
    cups_url: str = f"http://127.0.0.1:631{PRINTER_PATH}"
    state_dir: str = "/var/lib/hp-printer"
    issuer: str = ISSUER
    client_id: str = CLIENT_ID
    required_group: str = REQUIRED_GROUP
    max_request_bytes: int = 80 * 1024 * 1024

    @classmethod
    def load(cls, path: Path | None = None):
        if path is None:
            return cls()
        raw = tomllib.loads(path.read_text(encoding="utf-8")).get("gateway", {})
        unknown = set(raw) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown gateway settings: {', '.join(sorted(unknown))}")
        result = cls(**raw)
        if result.listen != "127.0.0.1":
            raise ValueError("Public gateway must listen on loopback behind Cloudflare Tunnel")
        if result.cups_url != cls.cups_url:
            raise ValueError("Only the existing local CUPS queue is supported in this release")
        return result
