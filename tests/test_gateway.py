import struct
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from hp_printer.auth import AuthError, owner_key
from hp_printer.config import ISSUER, GatewayConfig
from hp_printer.gateway import JobOwners, create_app
from hp_printer.ipp import Attribute, Group, parse, request


class Verifier:
    def verify(self, token):
        if token not in ("user-a", "user-b"):
            raise AuthError("denied")
        return {"iss": ISSUER, "sub": token}


@pytest.fixture
def environment(tmp_path):
    calls = []
    jobs = {}

    def backend(req):
        data = parse(req.content)
        calls.append(data)
        response = request()
        response.code = 0
        if data.code in (2, 5):
            jobs[42] = data.values(b"requesting-user-name")[0]
            response.groups.append(Group(2, [Attribute(0x21, b"job-id", struct.pack("!i", 42))]))
        if data.code == 9:
            response.groups.append(Group(2, [Attribute(0x42, b"job-originating-user-name", jobs.get(42, b"other"))]))
        return httpx.Response(200, content=response.encode())

    app = create_app(replace(GatewayConfig(), state_dir=str(tmp_path)), verifier=Verifier(), transport=httpx.MockTransport(backend))
    with TestClient(app) as client:
        yield client, calls


def send(client, message, token="user-a"):
    return client.post("/ipp/print", content=message.encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/ipp"})


def test_auth_before_upstream(environment):
    client, calls = environment
    assert client.post("/ipp/print", content=b"anything").status_code == 401
    assert send(client, request(), "invalid").status_code == 401
    assert calls == []


def test_read_and_submit_identity(environment):
    client, calls = environment
    assert send(client, request()).status_code == 200
    result = send(client, request(2))
    assert parse(result.content).job_id() == 42
    assert calls[-1].values(b"requesting-user-name")[0].startswith(b"icthub-")


def test_other_users_cannot_cancel(environment):
    client, calls = environment
    send(client, request(5))
    cancel = request(8)
    cancel.replace(b"job-id", 0x21, struct.pack("!i", 42))
    rejected = parse(send(client, cancel, "user-b").content)
    assert rejected.code == 0x0406
    assert len(calls) == 1
    assert parse(send(client, cancel).content).code == 0
    assert len(calls) == 3


def test_disallowed_operation_never_forwarded(environment):
    client, calls = environment
    assert parse(send(client, request(3)).content).code == 0x0400
    assert calls == []


def test_transport_error_is_not_retried(tmp_path):
    count = 0

    def failed(req):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("response lost")

    app = create_app(replace(GatewayConfig(), state_dir=str(tmp_path)), verifier=Verifier(), transport=httpx.MockTransport(failed))
    with TestClient(app) as client:
        assert send(client, request(2)).status_code == 502
    assert count == 1


def test_upload_limit_checked_before_cups(tmp_path):
    app = create_app(replace(GatewayConfig(), state_dir=str(tmp_path), max_request_bytes=10), verifier=Verifier())
    with TestClient(app) as client:
        assert send(client, request(2)).status_code == 413


def test_reused_cups_job_id_cannot_be_cancelled(tmp_path):
    calls = []

    def backend(req):
        incoming = parse(req.content)
        calls.append(incoming.code)
        response = request()
        response.code = 0
        response.groups.append(Group(2, [Attribute(0x42, b"job-originating-user-name", b"another-owner")]))
        return httpx.Response(200, content=response.encode())

    app = create_app(replace(GatewayConfig(), state_dir=str(tmp_path)), verifier=Verifier(), transport=httpx.MockTransport(backend))
    JobOwners(tmp_path / "jobs.db").record(42, owner_key({"iss": ISSUER, "sub": "user-a"}))
    cancel = request(8)
    cancel.replace(b"job-id", 0x21, struct.pack("!i", 42))
    with TestClient(app) as client:
        assert parse(send(client, cancel).content).code == 0x0406
    assert calls == [9]
