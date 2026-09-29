import asyncio

import httpx
from fastapi.testclient import TestClient

from hp_printer.agent import Routing, create_agent
from hp_printer.config import CUPS_UUID, LOCAL_PORT
from hp_printer.ipp import Attribute, Group, request


def printer_reply(uuid):
    message = request()
    message.code = 0
    message.groups.append(Group(4, [Attribute(0x45, b"printer-uuid", uuid.encode())]))
    return httpx.Response(200, content=message.encode())


def test_lan_printer_identity_and_route_pinning(tmp_path):
    async def scenario():
        routing = Routing(tmp_path)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: printer_reply(CUPS_UUID))) as client:
            assert await routing.route(client, None) == "lan"
            routing.pin(12, "remote")
            assert await routing.route(client, 12) == "remote"
            assert Routing(tmp_path).pins["12"] == "remote"
    asyncio.run(scenario())


def test_wrong_lan_device_does_not_receive_print_jobs(tmp_path):
    async def scenario():
        routing = Routing(tmp_path)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: printer_reply("urn:uuid:someone-else"))) as client:
            assert await routing.route(client, None) == "remote"
    asyncio.run(scenario())


def test_agent_rejects_browser_origin_and_dns_rebinding(tmp_path):
    with TestClient(create_agent(tmp_path), base_url=f"http://127.0.0.1:{LOCAL_PORT}", client=("127.0.0.1", 12345)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health", headers={"Origin": "https://example.test"}).status_code == 403
        assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 403
