"""Private JSON-line IPC for the GUI. No HTTP control port or password arguments."""

import contextlib
import json
import sys

import httpx

from .auth import AuthError
from .config import LOCAL_PORT, PUBLIC_URL
from .native_auth import NativeLogin
from .native_registration import NativeRegistration
from .windows import authorize_tokens, install, login, read_settings, uninstall


def run():
    output = sys.stdout

    def send(value):
        output.write(json.dumps(value, ensure_ascii=False) + "\n")
        output.flush()

    class Progress:
        def write(self, message):
            if message.strip():
                send({"event": "progress", "message": message.strip()})

        def flush(self):
            pass

    session = None
    registration = None
    try:
        # Two password fields can require up to 48 KiB when JSON escapes Unicode.
        while line := sys.stdin.readline(65537):
            if len(line) > 65536:
                break
            try:
                request = json.loads(line)
                command = request.get("command")
                values = request.get("values") or {}
                with contextlib.redirect_stdout(Progress()):
                    if command == "start-login":
                        if registration:
                            registration.close()
                            registration = None
                        if session:
                            session.close()
                        session = NativeLogin()
                        result = session.start()
                    elif command == "respond-login" and session:
                        result = session.respond(values)
                    elif command == "start-registration":
                        if session:
                            session.close()
                            session = None
                        if registration:
                            registration.close()
                        registration = NativeRegistration()
                        result = registration.start()
                    elif command == "submit-registration" and registration:
                        result = registration.submit(values)
                    elif command == "resend-registration" and registration:
                        result = registration.resend()
                    elif command == "reuse-login":
                        identity = login(reuse=True, allow_browser=False)
                        result = {"stage": "authenticated", "username": identity.get("username", "")}
                    elif command == "install":
                        install(gui_path=str(values["gui_path"]))
                        result = {"stage": "installed"}
                    elif command == "uninstall":
                        uninstall()
                        result = {"stage": "uninstalled"}
                    elif command == "status":
                        settings = read_settings()
                        result = {"stage": "status", "installed": bool(settings.get("port_name")), "running": False}
                        with httpx.Client(timeout=8, trust_env=False) as client:
                            try:
                                health = client.get(f"http://127.0.0.1:{LOCAL_PORT}/health").json()
                                if health.get("service") == "icthub-printer-agent":
                                    result.update({"running": True, "login_required": health.get("loginRequired"),
                                                   "route": health.get("route"), "version": health.get("version")})
                            except (httpx.HTTPError, ValueError):
                                pass
                            try:
                                response = client.get(PUBLIC_URL + "/v1/status")
                                if response.status_code == 200:
                                    result["printer"] = response.json()
                            except (httpx.HTTPError, ValueError):
                                pass
                    else:
                        raise AuthError("操作已过期，请重新打开安装器。")
                    if result.get("stage") == "authenticated" and session and session.tokens:
                        identity = authorize_tokens(session.tokens)
                        result["username"] = identity.get("username", "")
                        session.close()
                        session = None
                send({"event": "result", "ok": True, "result": result})
            except AuthError as exc:
                send({"event": "result", "ok": False, "message": str(exc)})
            except httpx.HTTPError:
                # HTTP exceptions contain OAuth URLs; never forward them to the UI/logs.
                send({"event": "result", "ok": False, "message": "暂时无法连接服务，请检查网络后重试。"})
            except RuntimeError as exc:
                send({"event": "result", "ok": False, "message": str(exc)[:1500]})
            except Exception:
                send({"event": "result", "ok": False, "message": "操作未完成。请关闭正在运行的旧安装器后重试；添加打印机时请允许 Windows 权限提示。"})
            finally:
                line = ""
                request = values = None
    finally:
        if session:
            session.close()
        if registration:
            registration.close()
