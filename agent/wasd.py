from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes

try:  # pragma: no cover - optional dependency
    import pydirectinput
except Exception:  # pragma: no cover - gracefully handle missing module
    pydirectinput = None

# ---------------------------------------------------------------------------
# ``SendInput`` helpers working with scan codes
# ---------------------------------------------------------------------------

PUL = ctypes.POINTER(ctypes.c_ulong)

logger = logging.getLogger(__name__)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001

if hasattr(ctypes, "windll"):
    _user32 = ctypes.windll.user32
else:
    _user32 = None


def _send_scan(scan: int, keyup: bool = False, extended: bool = False) -> None:
    """Send a single keyboard event using the provided scan code."""

    key = REVERSE_SCANCODES.get(scan)
    if pydirectinput is not None and key:
        if keyup:
            pydirectinput.keyUp(key)
        else:
            pydirectinput.keyDown(key)
        return

    if _user32 is None:
        return

    flags = KEYEVENTF_SCANCODE
    if keyup:
        flags |= KEYEVENTF_KEYUP
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY

    extra = ctypes.c_ulong(0)
    ki = KEYBDINPUT(
        wVk=0,
        wScan=scan,
        dwFlags=flags,
        time=0,
        dwExtraInfo=ctypes.pointer(extra),
    )
    inp = INPUT(type=INPUT_KEYBOARD, ki=ki)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


SCANCODES = {
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "i": 0x17,
    "space": 0x39,
    "shift": 0x2A,
    "ctrl": 0x1D,
    "alt": 0x38,
    "x": 0x2D,
    "up": 0x48,
    "down": 0x50,
    "left": 0x4B,
    "right": 0x4D,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
}

# Keys that require the extended flag when sent via ``SendInput``.
EXTENDED_KEYS = {"up", "down", "left", "right"}

# Virtual-key codes for the supported keys.  These values match the constants
# used by the Windows API.
VK_CODES = {
    "w": 0x57,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    "i": 0x49,
    "space": 0x20,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "x": 0x58,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
}

REVERSE_VK_CODES = {v: k for k, v in VK_CODES.items()}
REVERSE_SCANCODES = {v: k for k, v in SCANCODES.items()}


def resolve_key(key):
    """Normalize various key representations to a simple string.

    ``pynput`` may pass strings like ``Key.space`` or ``Key.shift`` but it can
    also provide objects exposing ``scan`` or ``vk`` attributes.  This helper
    accepts any of those forms as well as simple dictionaries used in tests.
    """

    # Simple string form such as ``Key.space`` or ``"w"``
    if isinstance(key, str):
        return key.split(".", 1)[1] if key.startswith("Key.") else key

    # Dict style: {"scan": 0x11} or {"vk": 0x57}
    if isinstance(key, dict):
        if "scan" in key:
            return REVERSE_SCANCODES.get(key["scan"], key["scan"])
        if "vk" in key:
            return REVERSE_VK_CODES.get(key["vk"], key["vk"])

    # Object with attributes ``scan``/``vk``/``char``
    for attr in ("char", "scan", "vk"):
        if hasattr(key, attr):
            val = getattr(key, attr)
            if val is None:
                continue
            if attr == "char":
                return val
            if attr == "scan":
                return REVERSE_SCANCODES.get(val, val)
            if attr == "vk":
                return REVERSE_VK_CODES.get(val, val)

    # Fallback to string representation
    sval = str(key)
    return sval.split(".", 1)[1] if sval.startswith("Key.") else sval


def key_down(scan: int, extended: bool = False) -> None:
    _send_scan(scan, extended=extended)


def key_up(scan: int, extended: bool = False) -> None:
    _send_scan(scan, keyup=True, extended=extended)


class KeyHold:
    def __init__(self, dry: bool = False, active_fn=None):
        """
        dry: jeśli True – nie wysyła realnych klawiszy (tryb testowy)
        active_fn: funkcja bezargumentowa -> bool (czy okno jest aktywne). Gdy False, watchdog zwalnia klawisze.
        """
        self.down = set()
        self.lock = threading.Lock()
        self.dry = dry
        self.active_fn = active_fn
        self._stop = False
        self._wd = threading.Thread(target=self._watchdog, daemon=True)
        self._wd.start()

    def _watchdog(self):
        while not self._stop:
            if self.active_fn is not None:
                try:
                    if not self.active_fn():
                        self.release_all()
                except Exception:
                    pass
            time.sleep(0.5)

    def stop(self):
        self._stop = True
        self.release_all()

    def _down(self, key: str) -> None:
        if self.dry or (self.active_fn is not None and not self.active_fn()):
            return
        scan = SCANCODES[key]
        extended = key in EXTENDED_KEYS
        if extended:
            key_down(scan, extended=True)
        else:
            key_down(scan)

    def _up(self, key: str) -> None:
        if self.dry or (self.active_fn is not None and not self.active_fn()):
            return
        scan = SCANCODES[key]
        extended = key in EXTENDED_KEYS
        if extended:
            key_up(scan, extended=True)
        else:
            key_up(scan)

    def press(self, key: str):
        with self.lock:
            if key not in self.down:
                logger.debug("Naciśnięto klawisz %s", key)
                self._down(key)
                self.down.add(key)

    def release(self, key: str):
        with self.lock:
            if key in self.down:
                logger.debug("Zwolniono klawisz %s", key)
                self._up(key)
                self.down.remove(key)

    def release_all(self):
        with self.lock:
            if self.down:
                logger.debug("Zwolniono wszystkie klawisze: %s", list(self.down))
            for k in list(self.down):
                self._up(k)
            self.down.clear()
