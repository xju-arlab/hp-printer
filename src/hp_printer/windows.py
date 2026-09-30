import argparse
import base64
import contextlib
import ctypes
import hashlib
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from . import __version__
from .auth import AuthError, TokenVerifier, browser_login, refresh_tokens
from .config import LOCAL_PORT, PRINTER_NAME, PUBLIC_URL
from .credentials import app_dir, load_tokens, save_tokens
from .windows_queue import configure_queue_script


def psquote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def powershell(script: str, *, timeout=180) -> str:
    wrapped = (
        "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); try { " + script
        + " } catch { [Console]::Error.WriteLine($_.FullyQualifiedErrorId + ': ' + $_.Exception.Message); exit 1 }"
    )
    encoded = base64.b64encode(wrapped.encode("utf-16le")).decode()
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        # Script content contains only paths, queue names and public URLs, never tokens.
        error = result.stderr.decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError("Windows 打印机配置失败：" + error)
    return result.stdout.decode("utf-8", errors="replace").strip()


def elevated_powershell(script: str) -> str:
    """Elevate queue configuration only; login and the agent stay with this user."""
    handle, filename = tempfile.mkstemp(prefix="printer-setup-", suffix=".json", dir=app_dir())
    os.close(handle)
    result_path = Path(filename)
    arguments_path = result_path.with_suffix(".args")
    elevated = (
        "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
        "try { $result = & { " + script + " }; "
        "$reply=@{ok=$true;output=($result -join [Environment]::NewLine)} } "
        "catch { $reply=@{ok=$false;error=$_.Exception.Message} }; "
        f"$reply | ConvertTo-Json -Compress | Set-Content -LiteralPath {psquote(filename)} -Encoding UTF8"
    )
    encoded = base64.b64encode(elevated.encode("utf-16le")).decode()
    try:
        # Avoid nesting the long configuration twice in EncodedCommand: it
        # would exceed CreateProcess's command-line limit after UTF-16/base64.
        arguments_path.write_text("-NoProfile -NonInteractive -EncodedCommand " + encoded, encoding="ascii")
        powershell(
            f"$arguments=Get-Content -LiteralPath {psquote(str(arguments_path))} -Raw; "
            "$p=Start-Process -FilePath powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru "
            "-ArgumentList $arguments; "
            "if($p.ExitCode -ne 0){throw '管理员打印机配置进程未正常完成。'}", timeout=300,
        )
        result = json.loads(result_path.read_text(encoding="utf-8-sig"))
        if not result.get("ok"):
            raise RuntimeError("Windows 打印机配置失败：" + result.get("error", "未知错误"))
        return result["output"]
    finally:
        result_path.unlink(missing_ok=True)
        arguments_path.unlink(missing_ok=True)


def read_settings() -> dict:
    try:
        settings = json.loads((app_dir() / "settings.json").read_text(encoding="utf-8-sig"))
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def write_settings(settings: dict):
    path = app_dir() / "settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def authorize_tokens(tokens: dict):
    with httpx.Client(timeout=30, trust_env=False) as client:
        result = client.get(PUBLIC_URL + "/v1/me", headers={"Authorization": "Bearer " + tokens["access_token"]})
    if result.status_code != 200 or result.json().get("authorized") is not True:
        raise AuthError("账号暂时无法使用打印服务，请确认邮箱已验证且账号处于启用状态。")
    save_tokens(tokens)
    return result.json()


def login(*, reuse: bool = False, allow_browser: bool = True):
    tokens = None
    if reuse:
        try:
            saved = load_tokens()
            try:
                TokenVerifier().verify(saved.get("access_token", ""))
                tokens = saved
            except AuthError:
                tokens = refresh_tokens(saved)
        except (OSError, ValueError, httpx.HTTPError):
            tokens = None
    if tokens is None:
        if not allow_browser:
            raise AuthError("请先登录算法与科研实验室账号。")
        tokens = browser_login()
    identity = authorize_tokens(tokens)
    print("账号验证成功。", flush=True)
    return identity


def stop_agent():
    destination = str(app_dir() / "ICTHubPrinter.exe")
    # The PID file can be missing after a partial installation. Match both the
    # executable and the agent command, including the PyInstaller parent.
    powershell(
        "$agents=@(Get-CimInstance Win32_Process -Filter \"Name='ICTHubPrinter.exe'\" | Where-Object { "
        f"$_.ExecutablePath -eq {psquote(destination)} -and $_.CommandLine -match ' agent(?: |$)'"
        "}); foreach($item in $agents){Stop-Process -Id $item.ProcessId -Force -ErrorAction SilentlyContinue}; "
        "foreach($item in $agents){Wait-Process -Id $item.ProcessId -Timeout 10 -ErrorAction SilentlyContinue}"
    )
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=0.3, trust_env=False)
        except httpx.HTTPError:
            return
        time.sleep(0.2)


def shortcut(path: Path, executable: str, arguments: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    powershell(
        "$s=New-Object -ComObject WScript.Shell; "
        f"$l=$s.CreateShortcut({psquote(str(path))}); "
        f"$l.TargetPath={psquote(executable)}; $l.Arguments={psquote(arguments)}; "
        "$l.WindowStyle=7; $l.Save()"
    )


def same_file_content(source: Path, destination: Path) -> bool:
    """Repeated installation of identical bytes must not restart the agent."""
    if not destination.is_file() or source.stat().st_size != destination.stat().st_size:
        return False
    with source.open("rb") as first, destination.open("rb") as second:
        return hashlib.file_digest(first, "sha256").digest() == hashlib.file_digest(second, "sha256").digest()


def replace_executable(source: Path, destination: Path, *, agent_file: bool = False):
    if source.resolve() == destination.resolve() or same_file_content(source, destination):
        return
    temporary = destination.with_suffix(".new.exe")
    try:
        shutil.copy2(source, temporary)
        if agent_file:
            stop_agent()
        # The PyInstaller parent can retain the executable briefly after the
        # agent's HTTP listener has closed.
        deadline = time.monotonic() + 15
        while True:
            try:
                os.replace(temporary, destination)
                return
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("旧程序仍在退出，请稍后重新安装。") from None
                time.sleep(0.25)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def installation_lock():
    """Serialize CLI/GUI changes to this user's files and startup entries."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    name = "Local\\ICTHubPrinterInstall-" + hashlib.sha256(str(app_dir()).encode()).hexdigest()[:12]
    mutex = kernel.CreateMutexW(None, True, name)
    already_running = ctypes.get_last_error() == 183
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if already_running:
            raise RuntimeError("安装正在进行，请等待当前安装完成。")
        yield
    finally:
        if not already_running:
            kernel.ReleaseMutex(mutex)
        kernel.CloseHandle(mutex)


def install(*, gui_path: str | None = None):
    with installation_lock():
        _install(gui_path=gui_path)


def _install(*, gui_path: str | None = None):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("请使用 GitHub Release 中的 EXE 安装程序。")
    login(reuse=True, allow_browser=gui_path is None)
    directory = app_dir()
    gui_destination = directory / "ICTHubPrinterSetup.exe"
    if gui_path:
        gui_source = Path(gui_path).resolve(strict=True)
        if gui_source.suffix.lower() != ".exe" or not gui_source.is_file():
            raise RuntimeError("安装程序路径无效，请重新下载安装包。")
        replace_executable(gui_source, gui_destination)
    print("正在安装打印后台…", flush=True)
    destination = directory / "ICTHubPrinter.exe"
    source = Path(sys.executable)
    try:
        replace_executable(source, destination, agent_file=True)
    except (OSError, RuntimeError):
        # If upgrading fails after stopping the old agent, leave the previous
        # installed binary available and restart it. Its mutex prevents a copy.
        if destination.is_file():
            subprocess.Popen([str(destination), "agent"], creationflags=subprocess.CREATE_NO_WINDOW,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise
    try:
        health = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=1, trust_env=False)
        if health.json().get("service") != "icthub-printer-agent":
            raise RuntimeError("本机 18765 端口被其他程序占用。")
    except httpx.HTTPError:
        subprocess.Popen([str(destination), "agent"], creationflags=subprocess.CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 45
    while True:
        try:
            health = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=1, trust_env=False)
            if health.status_code == 200 and health.json().get("service") == "icthub-printer-agent":
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("打印后台未能启动，请查看安装目录内 agent.log。")
        time.sleep(0.5)
    settings = read_settings()
    print("正在配置 Windows 打印机…", flush=True)
    owned_port = settings.get("port_name", "")
    configuration = configure_queue_script(owned_port if isinstance(owned_port, str) else "")
    try:
        output = powershell(configuration)
    except RuntimeError as exc:
        if "0x80070005" not in str(exc):
            raise
        print("Windows 需要管理员授权来添加打印机，请在权限确认窗口选择“是”。", flush=True)
        output = elevated_powershell(configuration)
    printer = json.loads(output)
    settings.update({"port_name": printer["PortName"], "version": __version__, "printer_name": PRINTER_NAME})
    write_settings(settings)
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/ICTHub Printer.lnk"
    start_script = f"Start-Process -WindowStyle Hidden -FilePath {psquote(str(destination))} -ArgumentList agent"
    args = "-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand " + base64.b64encode(start_script.encode("utf-16le")).decode()
    shortcut(startup, str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"), args)
    menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/ICTHub Printer"
    interface = gui_destination if gui_path else destination
    shortcut(menu / "登录打印机.lnk", str(interface), "login")
    shortcut(menu / "打印机状态.lnk", str(interface), "status")
    shortcut(menu / "卸载打印机.lnk", str(interface), "uninstall")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ICTHubPrinter") as key:
        for name, value in {
            "DisplayName": PRINTER_NAME, "DisplayVersion": __version__, "Publisher": "算法与科研实验室",
            "UninstallString": f'"{interface}" uninstall', "InstallLocation": str(directory),
            "DisplayIcon": str(interface),
        }.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    print(f"已安装：{PRINTER_NAME}\n现在可在 Word 中按 Ctrl+P 选择这台打印机。\nWindows 当前用户登录后会自动启动打印后台。", flush=True)


def uninstall():
    with installation_lock():
        _uninstall()


def _uninstall():
    settings = read_settings()
    if settings.get("port_name"):
        configuration = (
            f"$p=Get-Printer -Name {psquote(PRINTER_NAME)} -ErrorAction SilentlyContinue; "
            f"if($p -and $p.PortName -eq {psquote(settings['port_name'])}){{$p | Remove-Printer}}"
        )
        try:
            powershell(configuration)
        except RuntimeError as exc:
            if "0x80070005" not in str(exc):
                raise
            elevated_powershell(configuration)
    stop_agent()
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/ICTHub Printer.lnk"
    startup.unlink(missing_ok=True)
    menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/ICTHub Printer"
    for name in ("登录打印机.lnk", "打印机状态.lnk", "卸载打印机.lnk"):
        (menu / name).unlink(missing_ok=True)
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ICTHubPrinter")
    except FileNotFoundError:
        pass
    directory = app_dir().resolve()
    names = ["credentials.dpapi", "settings.json", "routes.json", "agent.pid"]
    for name in names:
        (directory / name).unlink(missing_ok=True)
    # Only this application's known executable is deleted, never recursive directory removal.
    executable = (directory / "ICTHubPrinter.exe").resolve()
    if executable.parent != directory:
        raise RuntimeError("Invalid uninstall path")
    gui_executable = directory / "ICTHubPrinterSetup.exe"
    # A running installed UI cannot be removed until the user closes it.
    script = (
        f"$paths=@({psquote(str(executable))},{psquote(str(gui_executable))}); "
        "for($i=0;$i -lt 120;$i++){Start-Sleep -Seconds 2; "
        "foreach($p in $paths){Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue}; "
        "if(-not ($paths | Where-Object {Test-Path -LiteralPath $_})){break}}"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode()
    subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
                     creationflags=subprocess.CREATE_NO_WINDOW)
    print("打印机、开机启动和本机登录凭据已移除。诊断日志保留在安装目录。")


def agent():
    import uvicorn

    from .agent import create_agent

    directory = app_dir()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, "Local\\ICTHubPrinter-" + hashlib.sha256(str(directory).encode()).hexdigest()[:12])
    if ctypes.get_last_error() == 183:
        return
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    logger = logging.getLogger("hp_printer")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(directory / "agent.log", maxBytes=1024*1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    (directory / "agent.pid").write_text(str(os.getpid()))
    try:
        uvicorn.run(create_agent(), host="127.0.0.1", port=LOCAL_PORT, access_log=False, proxy_headers=False, log_config=None)
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(mutex)


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="算法实验室·惠普打印机安装与登录")
    parser.add_argument("command", nargs="?", choices=["install", "login", "agent", "status", "uninstall", "remote-only", "auto-route", "gui-backend"], default="install")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--no-pause", action="store_true", help="Do not wait for Enter when launched from a terminal")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This application requires Windows 10/11")
    code = 0
    try:
        if args.command == "gui-backend":
            from .gui_backend import run
            run()
        elif args.command == "install":
            install()
        elif args.command == "login":
            login()
        elif args.command == "agent":
            agent()
        elif args.command == "uninstall":
            uninstall()
        elif args.command == "status":
            result = httpx.get(f"http://127.0.0.1:{LOCAL_PORT}/health", timeout=3, trust_env=False)
            print(json.dumps(result.json(), ensure_ascii=False, indent=2))
        else:
            settings = read_settings()
            settings["remote_only"] = args.command == "remote-only"
            write_settings(settings)
            print("已设置：" + ("强制公网通道" if settings["remote_only"] else "内网优先"))
    except (AuthError, RuntimeError, OSError, ValueError, httpx.HTTPError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        code = 1
    finally:
        if args.command not in ("agent", "gui-backend") and not args.no_pause and sys.stdin and sys.stdin.isatty():
            input("按 Enter 关闭窗口……")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
