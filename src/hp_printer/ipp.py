"""Bounded RFC 8010 attribute codec; document payload is kept byte-for-byte."""

import struct
from dataclasses import dataclass
from urllib.parse import urlsplit

from .config import PRINTER_NAME, PRINTER_PATH, PRINTER_UUID

MAX_ATTRIBUTES = 1024 * 1024
ALLOWED_OPERATIONS = {0x0002, 0x0004, 0x0005, 0x0006, 0x0008, 0x0009, 0x000A, 0x000B}
JOB_OPERATIONS = {0x0006, 0x0008, 0x0009}
CREATE_OPERATIONS = {0x0002, 0x0005}


class IPPError(ValueError):
    pass


@dataclass
class Attribute:
    tag: int
    name: bytes
    value: bytes


@dataclass
class Group:
    tag: int
    attributes: list[Attribute]


@dataclass
class Message:
    version: bytes
    code: int
    request_id: int
    groups: list[Group]
    document: bytes = b""

    def encode(self) -> bytes:
        out = bytearray(self.version + struct.pack("!HI", self.code, self.request_id))
        for group in self.groups:
            out.append(group.tag)
            for attr in group.attributes:
                out.append(attr.tag)
                out.extend(struct.pack("!H", len(attr.name)))
                out.extend(attr.name)
                out.extend(struct.pack("!H", len(attr.value)))
                out.extend(attr.value)
        out.append(3)
        out.extend(self.document)
        return bytes(out)

    def values(self, name: bytes, group_tag: int | None = None) -> list[bytes]:
        values = []
        for group in self.groups:
            if group_tag is not None and group.tag != group_tag:
                continue
            current = b""
            for attr in group.attributes:
                if attr.name:
                    current = attr.name
                if current == name:
                    values.append(attr.value)
        return values

    def replace(self, name: bytes, tag: int, value: bytes, group_tag: int = 1):
        groups = [g for g in self.groups if g.tag == group_tag]
        if not groups:
            raise IPPError("Missing operation attributes")
        for group in groups:
            current = b""
            kept = []
            for attr in group.attributes:
                if attr.name:
                    current = attr.name
                if current != name:
                    kept.append(attr)
            group.attributes = kept
        groups[0].attributes.append(Attribute(tag, name, value))

    def job_id(self) -> int | None:
        ids = self.values(b"job-id")
        numeric_id = None
        if ids:
            if len(ids) != 1 or len(ids[0]) != 4:
                raise IPPError("Invalid job ID")
            numeric_id = struct.unpack("!i", ids[0])[0]
        uris = self.values(b"job-uri", 1)
        if uris:
            if len(uris) != 1:
                raise IPPError("Invalid job URI")
            path = urlsplit(uris[0].decode("utf-8")).path
            if not path.startswith("/jobs/") or not path[6:].isdigit():
                raise IPPError("Invalid job URI")
            uri_id = int(path[6:])
            if numeric_id is not None and numeric_id != uri_id:
                raise IPPError("Conflicting job targets")
            numeric_id = uri_id
        if numeric_id is not None and numeric_id <= 0:
            raise IPPError("Invalid job ID")
        return numeric_id


def parse(data: bytes, *, allow_document: bool = True) -> Message:
    if len(data) < 9 or data[0] not in (1, 2):
        raise IPPError("Invalid IPP header")
    code, request_id = struct.unpack("!HI", data[2:8])
    groups = []
    group = None
    pos = 8
    while pos < min(len(data), MAX_ATTRIBUTES):
        tag = data[pos]
        pos += 1
        if tag == 3:
            if not groups or groups[0].tag != 1:
                raise IPPError("Missing operation attributes")
            if not allow_document and pos != len(data):
                raise IPPError("Unexpected document payload")
            return Message(data[:2], code, request_id, groups, data[pos:])
        if tag in (1, 2, 4, 5, 6, 7, 9):
            group = Group(tag, [])
            groups.append(group)
            continue
        if tag < 0x10 or tag == 0x7F or group is None:
            raise IPPError("Invalid attribute tag")
        if pos + 2 > len(data):
            break
        name_len = struct.unpack_from("!H", data, pos)[0]
        pos += 2
        if pos + name_len + 2 > len(data):
            break
        name = data[pos : pos + name_len]
        pos += name_len
        value_len = struct.unpack_from("!H", data, pos)[0]
        pos += 2
        if pos + value_len > len(data) or pos + value_len > MAX_ATTRIBUTES:
            break
        value = data[pos : pos + value_len]
        pos += value_len
        group.attributes.append(Attribute(tag, name, value))
    raise IPPError("Truncated or excessive IPP attributes")


def response_error(request: Message, code: int, message: str) -> bytes:
    attrs = [
        Attribute(0x47, b"attributes-charset", b"utf-8"),
        Attribute(0x48, b"attributes-natural-language", b"en"),
        Attribute(0x41, b"status-message", message.encode()),
    ]
    return Message(request.version, code, request.request_id, [Group(1, attrs)]).encode()


def request(code: int = 0x000B, uri: str = "ipp://localhost" + PRINTER_PATH) -> Message:
    return Message(b"\x02\x00", code, 1, [Group(1, [
        Attribute(0x47, b"attributes-charset", b"utf-8"),
        Attribute(0x48, b"attributes-natural-language", b"en"),
        Attribute(0x45, b"printer-uri", uri.encode()),
    ])])


def prepare_request(message: Message, authority: str, *, owner: str | None = None):
    if message.code not in ALLOWED_OPERATIONS:
        raise IPPError("IPP operation is not allowed")
    for name in (b"printer-uri", b"job-uri"):
        values = message.values(name, 1)
        if len(values) > 1:
            raise IPPError("Ambiguous target URI")
        if values:
            try:
                target = urlsplit(values[0].decode())
            except (UnicodeError, ValueError) as exc:
                raise IPPError("Invalid URI") from exc
            path = target.path
            valid = path.casefold() == PRINTER_PATH.casefold() if name == b"printer-uri" else (
                path.startswith("/jobs/") and path[6:].isdigit()
            )
            if not valid or target.query or target.fragment or target.username:
                raise IPPError("Only the configured printer is available")
            if name == b"printer-uri":
                # The Windows inbox IPP driver lowercases this URI attribute.
                path = PRINTER_PATH
            message.replace(name, 0x45, ("ipp://" + authority + path).encode())
    if message.code in JOB_OPERATIONS and not message.job_id():
        raise IPPError("A job ID is required")
    if owner is not None:
        message.replace(b"requesting-user-name", 0x42, owner.encode())
        if message.code == 0x000A:
            message.replace(b"my-jobs", 0x22, b"\x01")


def rewrite_response(message: Message, authority: str):
    """Expose one stable virtual printer; never leak a private URI to the driver."""
    for group in message.groups:
        seen = set()
        kept = []
        current = b""
        for attr in group.attributes:
            if attr.name:
                current = attr.name
            if attr.name in (b"media-default", b"sides-default"):
                key = (attr.name, attr.value)
                if key in seen:
                    continue
                seen.add(key)
            if attr.tag == 0x45 and not attr.value.startswith(b"urn:"):
                try:
                    uri = urlsplit(attr.value.decode())
                except (ValueError, UnicodeError):
                    uri = None
                if uri and uri.scheme in ("http", "https", "ipp", "ipps"):
                    path = uri.path
                    if not (path.startswith("/jobs/") or path == PRINTER_PATH):
                        path = PRINTER_PATH
                    scheme = "ipp" if uri.scheme.startswith("ipp") else "http"
                    attr.value = f"{scheme}://{authority}{path}".encode()
            if current in (b"printer-name", b"printer-info", b"printer-dns-sd-name"):
                attr.value = PRINTER_NAME.encode()
            if current == b"printer-uuid":
                attr.value = PRINTER_UUID.encode()
            kept.append(attr)
        group.attributes = kept
