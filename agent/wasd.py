from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
import time
import logging

from .keycodes import SCANCODES, EXTENDED_KEYS, VK_CODES


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

