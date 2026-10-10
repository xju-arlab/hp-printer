"""Security.framework generic-password item, without secrets in command arguments."""

import ctypes
from contextlib import contextmanager

SERVICE = "top.icthub.printer"
ACCOUNT = "oauth-tokens"
NOT_FOUND = -25300
DUPLICATE = -25299


class KeychainError(OSError):
    pass


class Keychain:
    def __init__(self):
        pointer = ctypes.c_void_p
        self.cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        for name, arguments, result in (
            ("CFStringCreateWithCString", [pointer, ctypes.c_char_p, ctypes.c_uint32], pointer),
            ("CFDataCreate", [pointer, pointer, ctypes.c_long], pointer),
            ("CFDictionaryCreateMutable", [pointer, ctypes.c_long, pointer, pointer], pointer),
            ("CFDictionarySetValue", [pointer, pointer, pointer], None),
            ("CFDataGetLength", [pointer], ctypes.c_long),
            ("CFDataGetBytePtr", [pointer], pointer),
            ("CFRelease", [pointer], None),
        ):
            function = getattr(self.cf, name)
            function.argtypes, function.restype = arguments, result
        for name, arguments in (
            ("SecItemCopyMatching", [pointer, ctypes.POINTER(pointer)]),
            ("SecItemAdd", [pointer, pointer]),
            ("SecItemUpdate", [pointer, pointer]),
            ("SecItemDelete", [pointer]),
        ):
            function = getattr(self.security, name)
            function.argtypes, function.restype = arguments, ctypes.c_int32

    def constant(self, name):
        library = self.cf if name == "kCFBooleanTrue" else self.security
        return ctypes.c_void_p.in_dll(library, name).value

    @contextmanager
    def dictionary(self, *, data=None, query=False, payload_only=False):
        # Entries remain alive until the dictionary is released; no callbacks needed.
        dictionary = self.cf.CFDictionaryCreateMutable(None, 0, None, None)
        owned = []

        def set_value(key, value):
            self.cf.CFDictionarySetValue(dictionary, self.constant(key), value)

        try:
            if not payload_only:
                set_value("kSecClass", self.constant("kSecClassGenericPassword"))
                for key, value in (("kSecAttrService", SERVICE), ("kSecAttrAccount", ACCOUNT)):
                    string = self.cf.CFStringCreateWithCString(None, value.encode(), 0x08000100)
                    owned.append(string)
                    set_value(key, string)
            if query:
                set_value("kSecReturnData", self.constant("kCFBooleanTrue"))
                set_value("kSecMatchLimit", self.constant("kSecMatchLimitOne"))
            if data is not None:
                buffer = ctypes.create_string_buffer(data)
                value = self.cf.CFDataCreate(None, buffer, len(data))
                owned.append(value)
                set_value("kSecValueData", value)
            yield dictionary
        finally:
            self.cf.CFRelease(dictionary)
            for value in owned:
                self.cf.CFRelease(value)

    @staticmethod
    def check(status):
        if status == NOT_FOUND:
            raise FileNotFoundError("请先登录算法与科研实验室账号。")
        if status != 0:
            raise KeychainError(f"无法访问 macOS 钥匙串（{status}），请解锁登录钥匙串并重试。")


def read() -> bytes:
    keychain = Keychain()
    result = ctypes.c_void_p()
    with keychain.dictionary(query=True) as query:
        keychain.check(keychain.security.SecItemCopyMatching(query, ctypes.byref(result)))
    try:
        size = keychain.cf.CFDataGetLength(result)
        if size < 1 or size > 128 * 1024:
            raise KeychainError("钥匙串中的打印授权无效，请重新登录。")
        return ctypes.string_at(keychain.cf.CFDataGetBytePtr(result), size)
    finally:
        keychain.cf.CFRelease(result)


def write(data: bytes):
    keychain = Keychain()
    with keychain.dictionary(data=data) as item:
        status = keychain.security.SecItemAdd(item, None)
    if status == DUPLICATE:
        with keychain.dictionary() as query, keychain.dictionary(data=data, payload_only=True) as update:
            status = keychain.security.SecItemUpdate(query, update)
    keychain.check(status)


def delete():
    keychain = Keychain()
    with keychain.dictionary() as query:
        status = keychain.security.SecItemDelete(query)
    if status != NOT_FOUND:
        keychain.check(status)
