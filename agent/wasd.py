from __future__ import annotations

import ctypes
from ctypes import wintypes
import threading
import time

# Selected virtual-key codes used by the agent.  These values normally come
# from ``win32con`` but are duplicated here to keep the module importable on
# non-Windows platforms (e.g. during tests in dry mode).
VK_SHIFT = 0x10
VK_SPACE = 0x20
VK_CONTROL = 0x11

VK_CODES = {
    "w": ord("W"),
    "a": ord("A"),
    "s": ord("S"),
    "d": ord("D"),
    "shift": VK_SHIFT,
    "space": VK_SPACE,
    "ctrl": VK_CONTROL,
    "x": ord("X"),
    "1": ord("1"),
    "2": ord("2"),
    "3": ord("3"),
    "4": ord("4"),
    "5": ord("5"),
    "6": ord("6"),
    "7": ord("7"),
    "8": ord("8"),
}


# ---------------------------------------------------------------------------
# Helpers around the ``SendInput`` Windows API
# ---------------------------------------------------------------------------

PUL = ctypes.POINTER(ctypes.c_ulong)


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


if hasattr(ctypes, "windll"):
    _user32 = ctypes.windll.user32
else:
    _user32 = None


def _send_input(vk: int, flags: int) -> None:
    """Low level wrapper over ``SendInput``.

    When running on non-Windows platforms ``_user32`` is ``None`` and the
    function becomes a no-op which keeps the module importable for tests.
    """

    if _user32 is None:
        return

    scan = _user32.MapVirtualKeyW(vk, 0)
    extra = ctypes.c_ulong(0)
    ki = KEYBDINPUT(
        wVk=vk,
        wScan=scan,
        dwFlags=flags,
        time=0,
        dwExtraInfo=ctypes.pointer(extra),
    )
    inp = INPUT(type=INPUT_KEYBOARD, ki=ki)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def key_down(vk: int) -> None:
    """Simulate key press for the given virtual-key code."""

    _send_input(vk, 0)


def key_up(vk: int) -> None:
    """Simulate key release for the given virtual-key code."""

    _send_input(vk, KEYEVENTF_KEYUP)


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

    def press(self, key: str):
        with self.lock:
            if key not in self.down:
                if not self.dry and (self.active_fn is None or self.active_fn()):
                    key_down(VK_CODES[key])
                self.down.add(key)

    def release(self, key: str):
        with self.lock:
            if key in self.down:
                if not self.dry and (self.active_fn is None or self.active_fn()):
                    key_up(VK_CODES[key])
                self.down.remove(key)

    def release_all(self):
        with self.lock:
            if not self.dry:
                for k in list(self.down):
                    key_up(VK_CODES[k])
            self.down.clear()
