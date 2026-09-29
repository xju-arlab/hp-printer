import argparse
import base64
import ctypes
import hashlib
import json
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from . import __version__
from .auth import AuthError, browser_login
from .config import LOCAL_PORT, LOCAL_URL, PRINTER_NAME, PUBLIC_URL
from .credentials import app_dir, save_tokens


def psquote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def powershell(script: str, *, timeout=180) -> str:
    encoded = base64.b64encode(("$ErrorActionPreference='Stop'; " + script).encode("utf-16le")).decode()
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        # Script content contains only paths, queue names and public URLs, never tokens.
        error = result.stderr.decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError("Windows 打印机配置失败：" + error)
    return result.stdout.decode("utf-8", errors="replace").strip()


def read_settings() -> dict:
    try:
        return json.loads((app_dir() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_settings(settings: dict):
    path = app_dir() / "settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def login():
    tokens = browser_login()
    with httpx.Client(timeout=30, trust_env=False) as client:
        result = client.get(PUBLIC_URL + "/v1/me", headers={"Authorization": "Bearer " + tokens["access_token"]})
    if result.status_code != 200 or result.json().get("authorized") is not True:
        raise AuthError("打印服务尚未授权这个账号，请联系管理员。")
    save_tokens(tokens)
    print("ICTHub 登录和打印权限验证成功。", flush=True)


def stop_agent():
    path = app_dir() / "agent.pid"
    try:
        pid = int(path.read_text())
    except (OSError, ValueError):
        return
    destination = str(app_dir() / "ICTHubPrinter.exe")
    powershell(
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; "
        f"if($p -and $p.ExecutablePath -eq {psquote(destination)} -and $p.CommandLine -match ' agent(?: |$)')"
        f"{{Stop-Process -Id {pid} -Force}}"
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


def install():
    if not getattr(sys, "frozen", False):
        raise RuntimeError("请使用 GitHub Release 中的 EXE 安装程序。")
    login()  # No system printer or autostart entry is installed before this succeeds.
    directory = app_dir()
    destination = directory / "ICTHubPrinter.exe"
    source = Path(sys.executable)
    if source.resolve() != destination.resolve():
        stop_agent()
        temporary = directory / "ICTHubPrinter.new.exe"
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
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
    owned_port = settings.get("port_name", "")
    output = powershell(
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
        f"$name={psquote(PRINTER_NAME)}; $p=Get-Printer -Name $name -ErrorAction SilentlyContinue; "
        f"if($p -and $p.PortName -ne {psquote(owned_port)}){{throw 'A different printer already uses this name'}}; "
        f"if(-not $p){{Add-Printer -Name $name -IppURL {psquote(LOCAL_URL)}; "
        "$p=Get-Printer -Name $name -ErrorAction Stop}; "
        "if($p.DriverName -ne 'Microsoft IPP Class Driver'){throw 'Unexpected printer driver'}; "
        "Set-PrintConfiguration -PrinterName $name -PaperSize A4 -Color $false -DuplexingMode OneSided; "
        "$p | Select-Object Name,PortName,DriverName | ConvertTo-Json -Compress"
    )
    printer = json.loads(output)
    settings.update({"port_name": printer["PortName"], "version": __version__, "printer_name": PRINTER_NAME})
    write_settings(settings)
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/ICTHub Printer.lnk"
    start_script = f"Start-Process -WindowStyle Hidden -FilePath {psquote(str(destination))} -ArgumentList agent"
    args = "-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand " + base64.b64encode(start_script.encode("utf-16le")).decode()
    shortcut(startup, str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"), args)
    menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/ICTHub Printer"
    shortcut(menu / "登录打印机.lnk", str(destination), "login")
    shortcut(menu / "打印机状态.lnk", str(destination), "status")
    shortcut(menu / "卸载打印机.lnk", str(destination), "uninstall")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ICTHubPrinter") as key:
        for name, value in {
            "DisplayName": PRINTER_NAME, "DisplayVersion": __version__, "Publisher": "XJU ICTHub",
            "UninstallString": f'"{destination}" uninstall', "InstallLocation": str(directory),
        }.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    print(f"已安装：{PRINTER_NAME}\n现在可在 Word 中按 Ctrl+P 选择这台打印机。\nWindows 当前用户登录后会自动启动打印后台。", flush=True)


def uninstall():
    settings = read_settings()
    if settings.get("port_name"):
        powershell(
            f"$p=Get-Printer -Name {psquote(PRINTER_NAME)} -ErrorAction SilentlyContinue; "
            f"if($p -and $p.PortName -eq {psquote(settings['port_name'])}){{$p | Remove-Printer}}"
        )
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
    script = f"Start-Sleep -Seconds 4; Remove-Item -LiteralPath {psquote(str(executable))} -Force -ErrorAction SilentlyContinue"
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
    parser = argparse.ArgumentParser(description="算法实验室·惠普打印机安装与登录")
    parser.add_argument("command", nargs="?", choices=["install", "login", "agent", "status", "uninstall", "remote-only", "auto-route"], default="install")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--no-pause", action="store_true", help="Do not wait for Enter when launched from a terminal")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This application requires Windows 10/11")
    code = 0
    try:
        if args.command == "install":
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
        if args.command != "agent" and not args.no_pause and sys.stdin and sys.stdin.isatty():
            input("按 Enter 关闭窗口……")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
