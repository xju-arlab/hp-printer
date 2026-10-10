"""macOS installer and per-user IPP bridge lifecycle."""

import argparse
import contextlib
import io
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from . import __version__
from .agent import create_agent
from .auth import AuthError, TokenVerifier, browser_login, refresh_tokens
from .config import (
    CUPS_UUID,
    LAN_URL,
    LOCAL_PORT,
    LOCAL_URL,
    PRINTER_NAME,
    PRINTER_PATH,
    PUBLIC_URL,
)
from .credentials import app_dir, load_tokens, save_tokens
from .ipp import IPPError, parse, request
from .macos_keychain import delete

QUEUE_NAME = "icthub_hp_deskjet_4900"
LABEL = "top.icthub.printer.agent"
AGENT_DIR = Path.home() / "Library/LaunchAgents"
PLIST = AGENT_DIR / f"{LABEL}.plist"
BACKEND = app_dir() / "ICTHubPrinterBackend"


def _run(command, *, timeout=30):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _admin_lpadmin(arguments):
    command = ["/usr/sbin/lpadmin", *arguments]
    result = _run(command, timeout=180)
    if result.returncode == 0:
        return
    shell_command = shlex.join(command)
    script = "do shell script " + _apple_string(shell_command) + " with administrator privileges"
    elevated = _run(["/usr/bin/osascript", "-e", script], timeout=240)
    if elevated.returncode:
        detail = (elevated.stderr or result.stderr).strip()
        if "User canceled" in detail:
            raise RuntimeError("未获得添加系统打印机所需的权限。")
        raise RuntimeError("macOS 未能添加打印机队列，请重试或检查系统打印机设置。")


def _apple_string(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lan_available():
    try:
        body = request(uri=f"ipp://192.168.5.87:631{PRINTER_PATH}").encode()
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.post(LAN_URL, content=body, headers={"Content-Type": "application/ipp"})
        info = parse(response.content, allow_document=False)
        return response.status_code == 200 and info.code < 0x400 and info.values(b"printer-uuid") == [CUPS_UUID.encode()]
    except (httpx.HTTPError, IPPError, OSError):
        return False


def _status():
    try:
        response = _run(["/usr/bin/lpstat", "-v", QUEUE_NAME])
        uri = response.stdout.partition(": ")[2].strip() if response.returncode == 0 else ""
        remote = "127.0.0.1" in uri
        route = "remote" if remote else ("lan" if uri else "")
        login_required = False
        if remote:
            try:
                health = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=0.5, trust_env=False).json()
                if health.get("service") == "icthub-printer-agent":
                    route = health.get("route") if health.get("route") in ("lan", "remote") else route
                    login_required = health.get("loginRequired") is True
            except (httpx.HTTPError, ValueError):
                pass
        try:
            tokens = load_tokens()
            TokenVerifier().verify(tokens.get("access_token", ""))
            logged_in = True
        except (AuthError, OSError, ValueError, KeyError):
            logged_in = False
        return {
            "stage": "status", "installed": bool(uri), "route": route,
            "loggedIn": logged_in, "loginRequired": login_required,
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"stage": "status", "installed": False, "route": "", "loggedIn": False}


def _authorize(allow_browser=True):
    tokens = None
    try:
        tokens = load_tokens()
        TokenVerifier().verify(tokens.get("access_token", ""))
    except (OSError, ValueError, KeyError):
        tokens = None
    except AuthError:
        try:
            tokens = refresh_tokens(tokens)
        except (AuthError, OSError, httpx.HTTPError):
            tokens = None
    if tokens is None:
        if not allow_browser:
            raise AuthError("请先登录实验室账号。")
        with contextlib.redirect_stdout(io.StringIO()):
            tokens = browser_login()
    TokenVerifier().verify(tokens.get("access_token", ""))
    try:
        with httpx.Client(timeout=20, trust_env=False) as client:
            response = client.get(PUBLIC_URL + "/v1/me", headers={"Authorization": "Bearer " + tokens["access_token"]})
        if response.status_code != 200 or response.json().get("authorized") is not True:
            raise AuthError("账号暂时无法使用打印服务，请确认邮箱已验证且账号处于启用状态。")
    except httpx.HTTPError as exc:
        raise AuthError("暂时无法连接打印服务，请检查网络后重试。") from exc
    save_tokens(tokens)


def _launchctl(*arguments):
    return _run(["/bin/launchctl", *arguments], timeout=20)


def _stop_agent():
    uid = os.getuid()
    _launchctl("bootout", f"gui/{uid}/{LABEL}")
    _launchctl("bootout", f"gui/{uid}", str(PLIST))
    PLIST.unlink(missing_ok=True)


def _start_agent():
    directory = app_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    if not getattr(sys, "frozen", False):
        raise RuntimeError("请从 DMG 中打开 ICTHub Printer 安装程序。")
    source = Path(sys.executable).resolve()
    if source != BACKEND.resolve():
        temporary = BACKEND.with_suffix(".new")
        shutil.copy2(source, temporary)
        temporary.chmod(0o755)
        os.replace(temporary, BACKEND)
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        PLIST.unlink()
    document = {
        "Label": LABEL,
        "ProgramArguments": [str(BACKEND), "--agent"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(directory / "agent.log"),
        "StandardErrorPath": str(directory / "agent.log"),
    }
    PLIST.write_bytes(plistlib.dumps(document))
    PLIST.chmod(0o600)
    uid = os.getuid()
    _launchctl("bootout", f"gui/{uid}/{LABEL}")
    loaded = _launchctl("bootstrap", f"gui/{uid}", str(PLIST))
    if loaded.returncode:
        raise RuntimeError("无法启动打印后台，请重新打开安装程序。")
    _launchctl("kickstart", "-k", f"gui/{uid}/{LABEL}")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=0.5, trust_env=False)
            if response.status_code == 200 and response.json().get("service") == "icthub-printer-agent":
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError("打印后台未能启动，请检查本机端口 18765 是否被占用。")


def _install():
    lan_available = _lan_available()
    if not lan_available:
        _authorize()
    _start_agent()
    uri = LOCAL_URL.replace("http://", "ipp://", 1)
    route = "lan" if lan_available else "remote"
    _admin_lpadmin([
        "-p", QUEUE_NAME, "-D", PRINTER_NAME, "-E", "-v", uri, "-m", "everywhere",
    ])
    return {"stage": "installed", "route": route}


def _login():
    _authorize()
    return {"stage": "authenticated"}


def _uninstall():
    current = _status()
    if current["installed"]:
        _admin_lpadmin(["-x", QUEUE_NAME])
    _stop_agent()
    delete()
    return {"stage": "uninstalled"}


def _agent():
    import uvicorn

    uvicorn.run(create_agent(), host="127.0.0.1", port=LOCAL_PORT, log_level="warning", access_log=False)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", choices=("status", "install", "login", "uninstall"))
    parser.add_argument("--agent", action="store_true")
    args = parser.parse_args()
    if args.agent:
        _agent()
        return
    try:
        if args.command == "status":
            result = _status()
        elif args.command == "install":
            result = _install()
        elif args.command == "login":
            result = _login()
        elif args.command == "uninstall":
            result = _uninstall()
        else:
            raise RuntimeError("操作未完成，请重新打开安装程序。")
        result.update({"ok": True, "version": __version__})
        print(json.dumps(result, ensure_ascii=False))
    except (AuthError, RuntimeError, OSError, httpx.HTTPError) as exc:
        print(json.dumps({"ok": False, "message": str(exc)[:1000]}, ensure_ascii=False))
    except Exception:
        print(json.dumps({"ok": False, "message": "操作未完成，请重试。"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
