from types import SimpleNamespace

import pytest

from hp_printer import windows
from hp_printer.auth import AuthError


@pytest.fixture
def login_environment(monkeypatch):
    saved = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, headers):
            assert url.endswith("/v1/me")
            assert headers["Authorization"].startswith("Bearer ")
            return SimpleNamespace(status_code=200, json=lambda: {"authorized": True})

    monkeypatch.setattr(windows.httpx, "Client", Client)
    monkeypatch.setattr(windows, "load_tokens", lambda: {"access_token": "saved"})
    monkeypatch.setattr(windows, "save_tokens", saved.append)
    monkeypatch.setattr(windows, "TokenVerifier", lambda: SimpleNamespace(verify=lambda _: {}))
    monkeypatch.setattr(windows, "browser_login", lambda: pytest.fail("Unexpected browser login"))
    return saved


def test_install_reuses_verified_credentials(login_environment):
    windows.login(reuse=True)
    assert login_environment == [{"access_token": "saved"}]


def test_install_refreshes_expired_credentials(login_environment, monkeypatch):
    def expired(_):
        raise AuthError("expired")

    monkeypatch.setattr(windows, "TokenVerifier", lambda: SimpleNamespace(verify=expired))
    monkeypatch.setattr(windows, "refresh_tokens", lambda _: {"access_token": "refreshed"})
    windows.login(reuse=True)
    assert login_environment == [{"access_token": "refreshed"}]


def test_explicit_login_still_opens_browser(login_environment, monkeypatch):
    monkeypatch.setattr(windows, "browser_login", lambda: {"access_token": "interactive"})
    windows.login()
    assert login_environment == [{"access_token": "interactive"}]
