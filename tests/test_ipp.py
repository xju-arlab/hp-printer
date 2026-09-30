import struct

import pytest

from hp_printer.config import PRINTER_PATH, PRINTER_UUID
from hp_printer.ipp import (
    Attribute,
    Group,
    IPPError,
    parse,
    prepare_request,
    request,
    rewrite_response,
)


def test_binary_document_roundtrip():
    message = request(2)
    message.document = b"%PDF-1.7\n\x00\x03\xffbinary\n"
    assert parse(message.encode()).encode() == message.encode()


def test_windows_lowercase_uri_is_canonicalized():
    message = request(uri="ipp://127.0.0.1:18765" + PRINTER_PATH.lower())
    prepare_request(message, "localhost:631")
    assert message.values(b"printer-uri") == [("ipp://localhost:631" + PRINTER_PATH).encode()]
    with pytest.raises(IPPError):
        prepare_request(request(uri="ipp://localhost/printers/another_queue"), "localhost:631")


@pytest.mark.parametrize("operation", [3, 7, 0x4001, 0x0010])
def test_uri_fetch_and_cups_admin_rejected(operation):
    with pytest.raises(IPPError):
        prepare_request(request(operation), "localhost:631", owner="verified-user")


def test_conflicting_job_targets_rejected():
    message = request(8)
    message.replace(b"job-id", 0x21, struct.pack("!i", 7))
    message.replace(b"job-uri", 0x45, b"ipp://localhost/jobs/8")
    with pytest.raises(IPPError, match="Conflicting"):
        prepare_request(message, "localhost:631", owner="verified-user")


def test_queue_constrained_and_username_replaced():
    message = request(2)
    message.replace(b"requesting-user-name", 0x42, b"root")
    prepare_request(message, "localhost:631", owner="icthub-user")
    assert message.values(b"requesting-user-name") == [b"icthub-user"]
    assert message.values(b"printer-uri") == [("ipp://localhost:631" + PRINTER_PATH).encode()]
    message.replace(b"printer-uri", 0x45, b"ipp://localhost/printers/other")
    with pytest.raises(IPPError):
        prepare_request(message, "localhost:631")


def test_response_rewrites_collection_uris_and_duplicate_defaults():
    message = request()
    message.code = 0
    message.groups.append(Group(4, [
        Attribute(0x44, b"media-default", b"iso_a4_210x297mm"),
        Attribute(0x44, b"media-default", b"iso_a4_210x297mm"),
        Attribute(0x45, b"printer-uuid", b"urn:uuid:original"),
        Attribute(0x34, b"printer-xri-supported", b""),
        Attribute(0x4A, b"", b"xri-uri"),
        Attribute(0x45, b"", ("ipp://private-host:631" + PRINTER_PATH).encode()),
        Attribute(0x37, b"", b""),
    ]))
    rewrite_response(message, "127.0.0.1:18765")
    encoded = message.encode()
    assert b"private-host" not in encoded
    assert message.values(b"printer-uuid") == [PRINTER_UUID.encode()]
    assert len(message.values(b"media-default")) == 1
    assert parse(encoded).encode() == encoded


@pytest.mark.parametrize("data", [b"", b"\x02\x00" + b"\x00"*7, request().encode()[:-1]])
def test_malformed_packets(data):
    with pytest.raises(IPPError):
        parse(data)
