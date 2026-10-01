import json
from urllib.parse import urlencode

import httpx
import pytest

from hp_printer.auth import AuthError
from hp_printer.native_auth import ORIGIN, NativeLogin
from hp_printer.native_registration import EXECUTOR_URL, NativeRegistration

EXECUTOR = ORIGIN + "/api/v3/flows/executor/default-provider-authorization-explicit-consent/?query="
CONSENT = {"component": "ak-stage-consent", "token": "synthetic-consent-token",
           "permissions": [], "additional_permissions": []}


@pytest.fixture
def login():
    session = NativeLogin()
    session.client.close()
    session.executor = EXECUTOR
    session.flow_page = ORIGIN + "/if/flow/default-provider-authorization-explicit-consent/"
    session.token_endpoint = ORIGIN + "/application/o/token/"
    yield session
    session.close()


@pytest.mark.parametrize("redirect_mode", ["http", "json"])
def test_consent_uses_authentik_csrf_after_cookie_rotation(login, monkeypatch, redirect_mode):
    login.challenge = dict(CONSENT)
    callback = login.callback + "?" + urlencode({"code": "synthetic-code", "state": login.state})
    exchanges = []

    def handle(request):
        if request.method == "GET":
            assert str(request.url) == EXECUTOR
            return httpx.Response(200, json=CONSENT, headers={
                "Set-Cookie": "authentik_csrf=rotated-value; Path=/; Secure",
            })
        if str(request.url) == EXECUTOR:
            # Authentik enforces this header once the session is authenticated.
            # The old X-CSRFToken header caused ak-stage-flow-error here.
            if request.headers.get("X-Authentik-CSRF") != "rotated-value":
                return httpx.Response(200, json={"component": "ak-stage-flow-error"})
            assert "X-CSRFToken" not in request.headers
            assert "authentik_csrf=rotated-value" in request.headers["Cookie"]
            assert request.headers["Origin"] == ORIGIN
            assert request.headers["Referer"] == login.flow_page
            assert json.loads(request.content) == {
                "component": "ak-stage-consent", "token": "synthetic-consent-token",
            }
            if redirect_mode == "http":
                return httpx.Response(302, headers={"Location": callback})
            return httpx.Response(200, json={"component": "xak-flow-redirect", "to": callback})
        assert str(request.url) == login.token_endpoint
        exchanges.append(request)
        return httpx.Response(200, json={"id_token": "synthetic-id", "access_token": "synthetic-access",
                                        "refresh_token": "synthetic-refresh"})

    verified = []

    class Verifier:
        def verify(self, token, **kwargs):
            verified.append((token, kwargs))
            return {"sub": "synthetic-user"}

    monkeypatch.setattr("hp_printer.native_auth.TokenVerifier", Verifier)
    login.client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=False)
    login.client.cookies.set("authentik_csrf", "old-value", domain="auth.icthub.top")
    assert login.advance(EXECUTOR)["stage"] == "consent"
    assert login.respond({"accept": True}) == {"stage": "authenticated"}
    assert len(exchanges) == 1
    assert verified == [("synthetic-id", {"nonce": login.nonce}), ("synthetic-access", {})]


@pytest.mark.parametrize(("challenge", "values", "field"), [
    ({"component": "ak-stage-identification", "password_fields": True},
     {"username": "synthetic", "password": "synthetic-password"}, "password"),
    ({"component": "ak-stage-password"}, {"password": "synthetic-password"}, "password"),
    ({"component": "ak-stage-authenticator-validate"}, {"code": "000000"}, "code"),
])
def test_login_stage_posts_authentik_csrf(login, challenge, values, field):
    def handle(request):
        assert request.headers["X-Authentik-CSRF"] == "synthetic-csrf"
        assert json.loads(request.content)[field] == values[field]
        return httpx.Response(200, json=CONSENT)

    login.client = httpx.Client(transport=httpx.MockTransport(handle))
    login.client.cookies.set("authentik_csrf", "synthetic-csrf", domain="auth.icthub.top")
    login.challenge = challenge
    assert login.respond(values)["stage"] == "consent"


def test_missing_cookie_does_not_submit_consent(login):
    def unexpected_request(_):
        pytest.fail("No POST should be sent without a CSRF cookie")

    login.client = httpx.Client(transport=httpx.MockTransport(unexpected_request))
    login.challenge = dict(CONSENT)
    with pytest.raises(AuthError, match="会话已过期"):
        login.respond({"accept": True})


def test_registration_posts_same_authentik_header():
    registration = NativeRegistration()
    registration.client.close()

    def handle(request):
        assert str(request.url) == EXECUTOR_URL
        assert request.headers["X-Authentik-CSRF"] == "synthetic-csrf"
        assert "X-CSRFToken" not in request.headers
        return httpx.Response(200, json={"component": "ak-stage-email"})

    registration.client = httpx.Client(transport=httpx.MockTransport(handle))
    registration.client.cookies.set("authentik_csrf", "synthetic-csrf", domain="auth.icthub.top")
    try:
        assert registration.post({"component": "ak-stage-prompt"})["stage"] == "registration-email"
    finally:
        registration.close()


def test_consent_descriptions_are_localized_and_unknown_permissions_remain_visible(login):
    login.challenge = {**CONSENT, "permissions": [
        {"id": "openid", "name": ""}, {"id": "profile", "name": "Internal profile description"},
        {"id": "email", "name": "Internal email description"},
        {"id": "groups", "name": "Internal print description"},
        {"id": "offline_access", "name": "Internal refresh description"},
    ], "additional_permissions": [{"id": "new-scope", "name": "New permission"}]}
    permissions = login.public_challenge()["permissions"]
    assert len(permissions) == 6
    assert "读取邮箱及验证状态" in permissions
    assert "New permission" in permissions
    assert not any("Internal" in text for text in permissions)


@pytest.mark.parametrize("request_id", ["a" * 32, "not-safe?token=secret"])
def test_server_error_does_not_echo_server_payload(login, request_id):
    login.challenge = {"component": "ak-stage-flow-error", "request_id": request_id,
                       "error": "sensitive-server-data", "traceback": "sensitive-traceback"}
    with pytest.raises(AuthError) as caught:
        login.public_challenge()
    message = str(caught.value)
    assert "登录服务未能完成授权" in message
    assert "sensitive" not in message and "secret" not in message
    assert ("记录编号" in message) == (request_id == "a" * 32)


def test_consent_validation_error_requests_confirmation_again(login):
    login.challenge = {**CONSENT, "response_errors": {"token": [{"string": "arbitrary text"}]}}
    assert login.public_challenge()["message"] == "授权确认已更新，请再次点击允许。"
