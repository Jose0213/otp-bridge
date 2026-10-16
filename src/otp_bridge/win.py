"""Windows bits: a global hotkey and typing text into the focused window."""
import ctypes
import logging
import threading
import time
from ctypes import wintypes

log = logging.getLogger("otp_bridge")

user32 = ctypes.WinDLL("user32", use_last_error=True)

MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
HELD_KEYS = (0x10, 0x11, 0x12, 0x5B, 0x5C)  # shift, ctrl, alt, lwin, rwin

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x2
KEYEVENTF_UNICODE = 0x4


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):  # only here so the union has the right size
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def parse_hotkey(spec: str):
    """'ctrl+alt+o' -> (modifiers, virtual key code)."""
    mods, vk = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in MODS:
            mods |= MODS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])
        else:
            raise ValueError(f"unknown key in hotkey: {part!r}")
    if vk is None:
        raise ValueError(f"hotkey needs a non-modifier key: {spec!r}")
    return mods, vk


def listen_hotkey(spec: str, callback) -> bool:
    """Register a global hotkey on a background thread. Returns False if it's taken."""
    mods, vk = parse_hotkey(spec)
    ready = threading.Event()
    result = {}

    def loop():
        ok = user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk)
        result["ok"] = bool(ok)
        ready.set()
        if not ok:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                try:
                    callback()
                except Exception:
                    log.exception("hotkey callback failed")

    threading.Thread(target=loop, daemon=True, name="hotkey").start()
    ready.wait(2)
    if not result.get("ok"):
        log.warning("could not register hotkey %s (in use by another app?)", spec)
    return result.get("ok", False)


def wait_for_modifiers_released(timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not any(user32.GetAsyncKeyState(k) & 0x8000 for k in HELD_KEYS):
            return
        time.sleep(0.02)


def type_text(text: str):
    """Type `text` into whatever window has focus."""
    inputs = []
    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inputs.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, ord(ch), flags, 0, 0))))
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        log.warning("SendInput typed %d of %d keystrokes", sent, len(inputs))
