"""Native client for the existing public Authentik enrollment flow."""

import re
import time

import httpx

from . import __version__
from .auth import AuthError
from .native_auth import ORIGIN

REGISTRATION_URL = ORIGIN + "/if/flow/icthub-public-registration/"
EXECUTOR_URL = ORIGIN + "/api/v3/flows/executor/icthub-public-registration/?query="
PENDING_FIELD = "attributes.icthub_pending_verification"
FIELDS = {"username": "username", "email": "email", "password": "password", "password_repeat": "password"}


class NativeRegistration:
    def __init__(self):
        self.client = httpx.Client(
            timeout=30, trust_env=False, follow_redirects=False,
            headers={"User-Agent": f"ICTHubPrinter/{__version__}", "Accept": "application/json"},
        )
        self.deadline = time.monotonic() + 1800
        self.component = ""
        self.has_pending_field = False
        self.resend_after = 0.0

    def close(self):
        self.client.cookies.clear()
        self.client.close()
        self.component = ""

    def check_deadline(self):
        if time.monotonic() > self.deadline:
            raise AuthError("注册已超时，请返回后重新开始；已收到验证邮件可继续使用其中的链接。")

    def start(self):
        self.check_deadline()
        # Establish Authentik's session/CSRF cookie without an OAuth request.
        response = self.client.get(REGISTRATION_URL)
        response.raise_for_status()
        return self.read(self.client.get(EXECUTOR_URL))

    def read(self, response):
        if response.status_code == 429:
            raise AuthError("操作太频繁，请稍后重试。")
        if response.status_code not in (200, 400):
            response.raise_for_status()
        challenge = response.json()
        component = challenge.get("component")
        if component == "ak-stage-access-denied":
            raise AuthError("注册服务暂时不可用，请稍后重试。")
        if component == "ak-stage-prompt":
            fields = challenge.get("fields") or []
            names = {field.get("field_key") for field in fields}
            if not set(FIELDS).issubset(names) or names - set(FIELDS) - {PENDING_FIELD}:
                raise AuthError("注册表单已调整，请更新安装器后重试。")
            if any(field.get("type") != FIELDS.get(field.get("field_key"), "hidden") for field in fields):
                raise AuthError("注册表单已调整，请更新安装器后重试。")
            self.component = component
            self.has_pending_field = PENDING_FIELD in names
            # Never echo server field values or arbitrary validation messages.
            errors = challenge.get("response_errors") or {}
            return {"stage": "registration", "message": self.error_message(errors)}
        if component == "ak-stage-email":
            first_email = self.component != component
            self.component = component
            if first_email:
                self.resend_after = time.monotonic() + 60
            return {"stage": "registration-email"}
        # Enrollment never creates a printer token or bypasses email verification.
        # The email link restores the flow in the user's mail/browser environment.
        raise AuthError("注册流程已改变，请返回后重试；已收到验证邮件可继续使用其中的链接。")

    @staticmethod
    def error_message(errors):
        if not errors:
            return ""
        if "username" in errors:
            return "请检查用户名格式，或换一个用户名。"
        if "email" in errors:
            return "请检查邮箱信息；已有账号可直接登录。"
        if "password_repeat" in errors:
            return "两次密码不一致，请重新确认。"
        if "password" in errors:
            return "密码未通过验证，请使用至少 8 位、包含字母和数字的密码。"
        return "注册信息未通过验证，请检查后重试；已有账号可直接登录。"

    def post(self, body):
        csrf = next((cookie.value for cookie in self.client.cookies.jar if cookie.name == "authentik_csrf"), "")
        if not csrf:
            raise AuthError("注册会话已过期，请返回后重新开始。")
        return self.read(self.client.post(EXECUTOR_URL, json=body, headers={
            "Origin": ORIGIN, "Referer": REGISTRATION_URL, "X-CSRFToken": csrf,
        }))

    def submit(self, values):
        self.check_deadline()
        username = str(values.get("username", "")).strip()
        email = str(values.get("email", "")).strip()
        password = str(values.get("password", ""))
        repeat = str(values.get("password_repeat", ""))
        if (not 3 <= len(username) <= 32 or not username[0].isalnum()
                or not all(character.isalnum() or character in "._-" for character in username)):
            raise AuthError("用户名需为 3–32 位，以字母或数字开头，可包含点、下划线和短横线。")
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise AuthError("请输入有效的邮箱。")
        if (not 8 <= len(password) <= 4096 or not any(character.isalpha() for character in password)
                or not any(character.isdigit() for character in password)):
            raise AuthError("密码至少 8 位，需包含字母和数字。")
        if repeat != password:
            raise AuthError("两次密码不一致，请重新确认。")
        # Recover from a lost POST response before creating anything again.
        current = self.read(self.client.get(EXECUTOR_URL))
        if current["stage"] == "registration-email":
            return current
        body = {"component": "ak-stage-prompt", "username": username, "email": email,
                "password": password, "password_repeat": repeat}
        if self.has_pending_field:
            body[PENDING_FIELD] = "true"
        return self.post(body)

    def resend(self):
        self.check_deadline()
        if self.component != "ak-stage-email":
            raise AuthError("请先提交注册信息。")
        remaining = int(max(0, self.resend_after - time.monotonic()) + 0.999)
        if remaining:
            raise AuthError(f"请在 {remaining} 秒后重新发送。")
        # Apply cooldown even if delivery/response fails; never retry automatically.
        self.resend_after = time.monotonic() + 60
        return self.post({"component": "ak-stage-email"})
