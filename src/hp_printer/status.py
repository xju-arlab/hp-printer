"""Read-only, cached printer telemetry. Public output uses an attribute allowlist."""

import asyncio
import struct
import time
from datetime import UTC, datetime

import httpx

from .config import PRINTER_NAME
from .ipp import MAX_ATTRIBUTES, Attribute, IPPError, parse, request

ATTRIBUTES = (
    b"printer-state", b"printer-state-reasons", b"printer-is-accepting-jobs",
    b"queued-job-count", b"marker-names", b"marker-levels", b"marker-types",
    b"marker-colors", b"marker-low-levels",
)
STATE = {3: "idle", 4: "processing", 5: "stopped"}
STATE_LABEL = {"idle": "空闲", "processing": "正在打印", "stopped": "已停止", "unknown": "暂不可读"}
INK_LABELS = {"tri-color ink": "彩色墨盒", "black ink": "黑色墨盒"}


def timestamp():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def decode(message):
    def texts(name):
        return [v.decode("utf-8", errors="replace")[:200] for v in message.values(name, 4)]

    def integers(name):
        return [struct.unpack("!i", v)[0] if len(v) == 4 else None for v in message.values(name, 4)]

    state = STATE.get(next(iter(integers(b"printer-state")), None), "unknown")
    reasons = list(dict.fromkeys(texts(b"printer-state-reasons")))[:32]
    normalized = {r.removesuffix("-error").removesuffix("-warning").removesuffix("-report") for r in reasons}
    paper_empty = "media-empty" in normalized if reasons else None
    paper_low = "media-low" in normalized if reasons else None
    levels, names = integers(b"marker-levels"), texts(b"marker-names")
    types, colors = texts(b"marker-types"), texts(b"marker-colors")
    thresholds = integers(b"marker-low-levels")
    supplies = []
    for i in range(min(max(len(names), len(levels)), 16)):
        raw_level = levels[i] if i < len(levels) else None
        level = raw_level if raw_level is not None and 0 <= raw_level <= 100 else None
        threshold = thresholds[i] if i < len(thresholds) else None
        original_name = names[i] if i < len(names) else f"耗材 {i + 1}"
        supplies.append({
            "name": INK_LABELS.get(original_name.lower(), original_name),
            "type": types[i] if i < len(types) else "unknown",
            "color": colors[i] if i < len(colors) else None,
            "levelPercent": level, "levelRaw": raw_level,
            "levelLabel": f"约 {level}%" if level is not None else "暂不可读",
            "low": level <= threshold if level is not None and threshold is not None else None,
            "lowThresholdPercent": threshold,
        })
    accepting = message.values(b"printer-is-accepting-jobs", 4)
    return {
        "reachable": True, "stale": False, "observedAt": timestamp(),
        "state": state, "stateLabel": STATE_LABEL[state], "reasons": reasons,
        "paperEmpty": paper_empty, "paperLow": paper_low,
        "paperLabel": "缺纸" if paper_empty else ("纸张不足" if paper_low else ("未报告缺纸" if reasons else "暂不可读")),
        "acceptingJobs": accepting[0] == b"\x01" if accepting else None,
        "queuedJobCount": next(iter(integers(b"queued-job-count")), None),
        "supplies": supplies,
    }


class PrinterStatus:
    def __init__(self, cups_url):
        self.cups_url = cups_url
        self.lock = asyncio.Lock()
        self.checked_at = 0.0
        self.cached = None
        self.previous = {}

    async def read_source(self, client, name, url):
        message = request(uri=url.replace("http://", "ipp://", 1))
        message.replace(b"requested-attributes", 0x44, ATTRIBUTES[0])
        message.groups[0].attributes.extend(Attribute(0x44, b"", item) for item in ATTRIBUTES[1:])
        try:
            async with client.stream("POST", url, content=message.encode(),
                                     headers={"Content-Type": "application/ipp"}, timeout=4) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_ATTRIBUTES:
                        raise IPPError("Excessive status response")
            parsed = parse(bytes(content), allow_document=False)
            if parsed.code >= 0x0400:
                raise IPPError("Status unavailable")
            result = decode(parsed)
            self.previous[name] = result
            return result
        except (httpx.HTTPError, IPPError, ValueError):
            # Keep the last readings with explicit age/stale flags, never fake 0% ink.
            previous = self.previous.get(name, {
                "observedAt": None, "state": "unknown", "stateLabel": "暂不可读", "reasons": [],
                "paperEmpty": None, "paperLow": None, "paperLabel": "暂不可读",
                "acceptingJobs": None, "queuedJobCount": None, "supplies": [],
            })
            return {**previous, "reachable": False, "stale": True, "error": "unreachable"}

    async def get(self, client):
        async with self.lock:
            if self.cached is not None and time.monotonic() - self.checked_at < 15:
                return self.cached
            device, queue = await asyncio.gather(
                self.read_source(client, "device", "http://127.0.0.1:60000/ipp/print"),
                self.read_source(client, "queue", self.cups_url),
            )
            self.cached = {
                "schemaVersion": 1, "printerName": PRINTER_NAME, "model": "HP DeskJet 4900 series",
                "checkedAt": timestamp(), "observedAt": device["observedAt"], "refreshAfterSeconds": 15,
                "online": device["reachable"], "stale": device["stale"],
                "state": device["state"] if device["reachable"] else "unknown",
                "stateLabel": device["stateLabel"] if device["reachable"] else "暂时无法读取设备",
                "paperEmpty": device["paperEmpty"] if device["reachable"] else None,
                "paperLow": device["paperLow"] if device["reachable"] else None,
                "paperLabel": device["paperLabel"] if device["reachable"] else "暂不可读",
                "supplies": device["supplies"], "suppliesApproximate": True,
                "source": "device", "device": device, "queue": queue,
                "paperReportsDiffer": (
                    device["paperEmpty"] != queue["paperEmpty"]
                    if device["reachable"] and queue["reachable"]
                    and device["paperEmpty"] is not None and queue["paperEmpty"] is not None else None
                ),
            }
            self.checked_at = time.monotonic()
            return self.cached
