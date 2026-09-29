"""Current-user Windows DPAPI storage; plaintext tokens never touch disk."""

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


def app_dir() -> Path:
    if os.name != "nt":
        raise RuntimeError("The printer installer and credential store require Windows")
    path = Path(os.environ["LOCALAPPDATA"]) / "ICTHubPrinter"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]


def _crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt32.CryptProtectData(ctypes.byref(source), "ICTHub Printer", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(target.data)


def save_tokens(tokens: dict):
    path = app_dir() / "credentials.dpapi"
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(_crypt(json.dumps(tokens).encode()))
    os.replace(temporary, path)


def load_tokens() -> dict:
    return json.loads(_crypt((app_dir() / "credentials.dpapi").read_bytes(), decrypt=True))
