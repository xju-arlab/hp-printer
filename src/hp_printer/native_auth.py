"""Authentik flow executor for the Windows UI; credentials stay in memory.

The authorization code, PKCE, state, nonce and token checks are the same as
the browser client. This does not use the resource owner password grant.
"""

import hashlib
import hmac
import re
import secrets
import time
from base64 import urlsafe_b64encode
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx

from . import __version__
from .auth import AuthError, TokenVerifier
from .config import CALLBACK_PORT, CLIENT_ID, ISSUER

ORIGIN = "https://auth.icthub.top"


class NativeLogin:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30, trust_env=False, follow_redirects=False,
            headers={"User-Agent": f"ICTHubPrinter/{__version__}", "Accept": "application/json"},
        )
        self.state, self.nonce, self.verifier = (secrets.token_urlsafe(40) for _ in range(3))
        self.callback = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
        self.deadline = time.monotonic() + 600
        self.executor = ""
        self.flow_page = ""
        self.challenge = {}
        self.tokens = None

    def close(self):
        self.client.cookies.clear()
        self.client.close()
        self.challenge = {}
        self.tokens = None
        self.verifier = ""

    @staticmethod
    def trusted_url(value):
        url = urljoin(ORIGIN + "/", value)
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "auth.icthub.top"
                or parsed.fragment or parsed.username or parsed.password):
            raise AuthError("登录服务返回了无法信任的地址，请联系管理员。")
        return url

    def check_deadline(self):
        if time.monotonic() > self.deadline:
            raise AuthError("登录已超时，请返回并重新登录。")

    def start(self):
        self.check_deadline()
        response = self.client.get(ISSUER + ".well-known/openid-configuration")
        response.raise_for_status()
        metadata = response.json()
        if metadata.get("issuer") != ISSUER:
            raise AuthError("登录服务标识不匹配。")
        self.token_endpoint = self.trusted_url(metadata["token_endpoint"])
        challenge = urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        url = self.trusted_url(metadata["authorization_endpoint"]) + "?" + urlencode({
            "client_id": CLIENT_ID, "response_type": "code", "redirect_uri": self.callback,
            "scope": "openid profile email groups offline_access", "state": self.state,
            "nonce": self.nonce, "code_challenge": challenge, "code_challenge_method": "S256",
        })
        return self.advance(url)

    def advance(self, url):
        for _ in range(24):
            self.check_deadline()
            parsed = urlsplit(url)
            if f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == self.callback:
                return self.finish(url)  # Never send a request to the loopback callback.
            url = self.trusted_url(url)
            response = self.client.get(url)
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            parsed = urlsplit(url)
            flow = re.fullmatch(r"/if/flow/([A-Za-z0-9_-]+)/?", parsed.path)
            if flow:
                self.flow_page = url
                # Preserve the original query, including the OAuth next parameter.
                self.executor = ORIGIN + f"/api/v3/flows/executor/{flow[1]}/?" + urlencode({"query": parsed.query})
                url = self.executor
                continue
            if parsed.path.startswith("/api/v3/flows/executor/"):
                challenge = response.json()
                if challenge.get("component") == "xak-flow-redirect":
                    url = urljoin(url, challenge["to"])
                    continue
                self.challenge = challenge
                return self.public_challenge()
            raise AuthError("登录流程返回了无法识别的页面，请联系管理员。")
        raise AuthError("登录流程跳转次数过多，请重新登录。")

    def public_challenge(self):
        challenge = self.challenge
        component = challenge.get("component")
        errors = challenge.get("response_errors") or {}
        # Do not echo server field values: they can contain the submitted identifier.
        message = "账号、密码或验证码未通过验证，请检查后重试。" if errors else ""
        common = {"message": message}
        if component == "ak-stage-identification":
            if challenge.get("captcha_stage"):
                raise AuthError("此账号的登录流程要求图形验证码，当前安装器暂不支持。")
            return {**common, "stage": "identity", "password": bool(challenge.get("password_fields"))}
        if component == "ak-stage-password":
            return {**common, "stage": "password"}
        if component == "ak-stage-authenticator-validate":
            devices = challenge.get("device_challenges") or []
            if not any(d.get("device_class") in ("totp", "static") for d in devices):
                raise AuthError("此账号需要安全密钥或其他验证方式；当前安装器支持动态验证码和恢复码。")
            return {**common, "stage": "code"}
        if component == "ak-stage-consent":
            permissions = challenge.get("permissions", []) + challenge.get("additional_permissions", [])
            return {**common, "stage": "consent", "permissions": [
                str(p.get("name", ""))[:200] for p in permissions
            ][:20]}
        if component == "ak-stage-access-denied":
            raise AuthError("账号暂时无法使用打印服务，请确认邮箱已验证且账号处于启用状态。")
        raise AuthError("账号要求的验证步骤暂不受安装器支持，请联系管理员。")

    def respond(self, values):
        self.check_deadline()
        component = self.challenge.get("component")
        body = {"component": component}
        if component == "ak-stage-identification":
            body["uid_field"] = str(values.get("username", "")).strip()[:254]
            if self.challenge.get("password_fields"):
                body["password"] = str(values.get("password", ""))[:4096]
        elif component == "ak-stage-password":
            body["password"] = str(values.get("password", ""))[:4096]
        elif component == "ak-stage-authenticator-validate":
            body["code"] = str(values.get("code", "")).strip()[:128]
        elif component == "ak-stage-consent" and values.get("accept") is True:
            body["token"] = self.challenge["token"]
        else:
            raise AuthError("登录步骤不匹配，请重新登录。")
        csrf = next((c.value for c in self.client.cookies.jar if c.name == "authentik_csrf"), "")
        response = self.client.post(self.executor, json=body, headers={
            "Origin": ORIGIN, "Referer": self.flow_page, "X-CSRFToken": csrf,
        })
        if response.is_redirect:
            return self.advance(urljoin(self.executor, response.headers["location"]))
        # Validation failures use a challenge with response_errors, including HTTP 400.
        if response.status_code != 400:
            response.raise_for_status()
        self.challenge = response.json()
        if self.challenge.get("component") == "xak-flow-redirect":
            return self.advance(urljoin(self.executor, self.challenge["to"]))
        return self.public_challenge()

    def finish(self, url):
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if (parsed.fragment or len(query.get("state", [])) != 1
                or not hmac.compare_digest(query["state"][0], self.state)):
            raise AuthError("登录状态校验失败，请重新登录。")
        if "error" in query or len(query.get("code", [])) != 1:
            raise AuthError("登录授权未完成，请重新登录。")
        response = self.client.post(self.token_endpoint, data={
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "code": query["code"][0], "redirect_uri": self.callback, "code_verifier": self.verifier,
        })
        if response.status_code != 200:
            raise AuthError("登录授权交换失败，请重新登录。")
        tokens = response.json()
        verifier = TokenVerifier()
        identity = verifier.verify(tokens.get("id_token", ""), nonce=self.nonce)
        access = verifier.verify(tokens.get("access_token", ""))
        if identity["sub"] != access["sub"] or not tokens.get("refresh_token"):
            raise AuthError("账号授权信息不完整，请联系管理员。")
        tokens["obtained_at"] = time.time()
        self.tokens = tokens
        return {"stage": "authenticated"}
