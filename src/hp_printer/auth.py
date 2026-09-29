import hashlib
import hmac
import secrets
import time
import webbrowser
from base64 import urlsafe_b64encode
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt

from .config import CALLBACK_PORT, CLIENT_ID, ISSUER, REQUIRED_GROUP


class AuthError(ValueError):
    pass


class TokenVerifier:
    def __init__(self, issuer=ISSUER, client_id=CLIENT_ID, required_group=REQUIRED_GROUP):
        if not issuer.startswith("https://"):
            raise ValueError("OIDC issuer requires HTTPS")
        self.issuer = issuer
        self.client_id = client_id
        self.required_group = required_group
        self.keys = jwt.PyJWKClient(issuer + "jwks/", timeout=12, lifespan=300)

    def verify(self, token: str, *, nonce: str | None = None) -> dict:
        if not token or len(token) > 32768:
            raise AuthError("Missing or excessive token")
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], audience=self.client_id,
                issuer=self.issuer, leeway=20,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
        except (jwt.PyJWTError, ValueError, OSError) as exc:
            raise AuthError("Login expired or invalid; sign in again") from exc
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthError("Missing subject")
        if claims.get("email_verified") is not True or not claims.get("email"):
            raise AuthError("Verify your Authentik email before installing")
        groups = claims.get("groups")
        if not isinstance(groups, list) or self.required_group not in groups:
            raise AuthError("This account has not been granted printer access")
        if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise AuthError("OIDC nonce mismatch")
        return claims


def owner_key(claims: dict) -> str:
    digest = hashlib.sha256((claims["iss"] + "\0" + claims["sub"]).encode()).hexdigest()
    return "icthub-" + digest[:32]


def browser_login(timeout: int = 600) -> dict:
    """Native public client using PKCE and an exact loopback callback."""
    state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = (
                self.client_address[0] == "127.0.0.1"
                and self.headers.get("Host") == f"127.0.0.1:{CALLBACK_PORT}"
                and parsed.path == "/callback"
                and len(params.get("state", [])) == 1
                and hmac.compare_digest(params["state"][0], state)
            )
            if not valid:
                self.send_error(400, "Invalid login callback")
                return
            if "error" in params:
                result["error"] = "Authentik denied the login"
            elif len(params.get("code", [])) == 1:
                result["code"] = params["code"][0]
            else:
                self.send_error(400, "Missing authorization code")
                return
            content = "登录结果已收到，请返回打印机安装程序。此窗口可以关闭。".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass  # OAuth authorization codes must never enter access logs.

    with HTTPServer(("127.0.0.1", CALLBACK_PORT), Callback) as server:
        server.timeout = 1
        with httpx.Client(timeout=20) as client:
            metadata = client.get(ISSUER + ".well-known/openid-configuration")
            metadata.raise_for_status()
            config = metadata.json()
            if config.get("issuer") != ISSUER:
                raise AuthError("Unexpected identity provider")
            for key in ("authorization_endpoint", "token_endpoint"):
                if urlsplit(config[key]).netloc != "auth.icthub.top" or not config[key].startswith("https://"):
                    raise AuthError("Unexpected OIDC endpoint")
            url = config["authorization_endpoint"] + "?" + urlencode({
                "client_id": CLIENT_ID, "response_type": "code", "redirect_uri": redirect,
                "scope": "openid profile email groups offline_access", "state": state,
                "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
            })
            print("请在打开的浏览器中登录 ICTHub，并允许打印机应用访问。", flush=True)
            if not webbrowser.open(url):
                raise AuthError("Could not open the system browser")
            deadline = time.monotonic() + timeout
            while not result and time.monotonic() < deadline:
                server.handle_request()
            if not result or "error" in result:
                raise AuthError(result.get("error", "Login timed out; run the installer again"))
            reply = client.post(config["token_endpoint"], data={
                "grant_type": "authorization_code", "client_id": CLIENT_ID,
                "code": result["code"], "redirect_uri": redirect, "code_verifier": verifier,
            })
            if reply.status_code != 200:
                raise AuthError("Authorization code exchange failed")
            tokens = reply.json()
    check = TokenVerifier()
    check.verify(tokens.get("id_token", ""), nonce=nonce)
    check.verify(tokens.get("access_token", ""))
    if not tokens.get("refresh_token"):
        raise AuthError("The printer application must allow offline_access")
    tokens["obtained_at"] = time.time()
    return tokens


def refresh_tokens(tokens: dict) -> dict:
    with httpx.Client(timeout=20) as client:
        reply = client.post("https://auth.icthub.top/application/o/token/", data={
            "grant_type": "refresh_token", "client_id": CLIENT_ID,
            "refresh_token": tokens.get("refresh_token", ""),
        })
    if reply.status_code != 200:
        raise AuthError("登录授权已失效，请重新运行安装包并选择登录。")
    fresh = reply.json()
    TokenVerifier().verify(fresh.get("access_token", ""))
    if "refresh_token" not in fresh:
        fresh["refresh_token"] = tokens["refresh_token"]
    fresh["obtained_at"] = time.time()
    return fresh
