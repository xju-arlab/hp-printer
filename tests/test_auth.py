import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from hp_printer.auth import AuthError, TokenVerifier
from hp_printer.config import CLIENT_ID, ISSUER, REQUIRED_GROUP


@pytest.fixture
def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = TokenVerifier()
    verifier.keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))
    claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": "synthetic-user", "iat": int(time.time()),
              "exp": int(time.time())+300, "email": "test@example.test", "email_verified": True,
              "groups": [REQUIRED_GROUP], "nonce": "expected"}
    return key, verifier, claims


def test_signed_verified_member(signed):
    key, verifier, claims = signed
    assert verifier.verify(jwt.encode(claims, key, algorithm="RS256"), nonce="expected")["sub"] == "synthetic-user"


@pytest.mark.parametrize("changes", [
    {"email_verified": False}, {"email_verified": "true"}, {"groups": []},
    {"aud": "other-client"}, {"iss": "https://other.example/"}, {"exp": 1},
    {"email": ""}, {"sub": ""},
])
def test_unauthorized_claims_rejected(signed, changes):
    key, verifier, claims = signed
    claims.update(changes)
    with pytest.raises(AuthError):
        verifier.verify(jwt.encode(claims, key, algorithm="RS256"))


def test_invalid_signature_and_nonce(signed):
    key, verifier, claims = signed
    forged = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthError):
        verifier.verify(jwt.encode(claims, forged, algorithm="RS256"))
    with pytest.raises(AuthError):
        verifier.verify(jwt.encode(claims, key, algorithm="RS256"), nonce="other")


def test_jwks_request_identifies_application():
    verifier = TokenVerifier()
    assert verifier.keys.headers["User-Agent"].startswith("ICTHubPrinter/")
    assert verifier.keys.headers["Accept"] == "application/json"


def test_jwks_outage_is_reported_as_network_error():
    def unavailable(_):
        raise jwt.PyJWKClientConnectionError("HTTP 403")

    verifier = TokenVerifier()
    verifier.keys = SimpleNamespace(get_signing_key_from_jwt=unavailable)
    with pytest.raises(AuthError, match="检查网络"):
        verifier.verify("synthetic-token")
