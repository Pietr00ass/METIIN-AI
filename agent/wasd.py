from __future__ import annotations

import logging
import threading
import time

try:  # pragma: no cover - optional dependency
    import pydirectinput

    pydirectinput.PAUSE = 0
    pydirectinput.FAILSAFE = False
except Exception:  # pragma: no cover - gracefully handle missing module
    pydirectinput = None

logger = logging.getLogger(__name__)

# ``_user32`` is kept for backward compatibility but is unused when relying
# solely on ``pydirectinput``.
_user32 = None


def _send_scan(scan: int, keyup: bool = False, extended: bool = False) -> None:
    """Send a single keyboard event using ``pydirectinput``.

    ``scan`` is looked up in :data:`REVERSE_SCANCODES` to obtain the key name.
    The ``extended`` flag is accepted for API compatibility but ignored.
    """

    if pydirectinput is None:
        return

    key = REVERSE_SCANCODES.get(scan)
    if not key:
        logger.warning("Unknown scancode %r", scan)
        return

    func = pydirectinput.keyUp if keyup else pydirectinput.keyDown
    try:
        result = func(key, _pause=False)
        if result is False:
            logger.warning("pydirectinput.%s returned False for %r", func.__name__, key)
    except Exception:  # pragma: no cover - log but do not raise
        logger.warning(
            "pydirectinput.%s failed for %r", func.__name__, key, exc_info=True
        )


SCANCODES = {
    "w": 0x11,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "e": 0x12,
    "i": 0x17,
    "space": 0x39,
    "shift": 0x2A,
    "ctrl": 0x1D,
    "alt": 0x38,
    # Hotkey for teleport (Ctrl+X); channel switching uses NumPad1..8
    "x": 0x2D,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    # Numeric keypad keys allow configuring channel hotkeys to e.g. ``numpad1``
    "numpad1": 0x4F,
    "numpad2": 0x50,
    "numpad3": 0x51,
    "numpad4": 0x4B,
    "numpad5": 0x4C,
    "numpad6": 0x4D,
    "numpad7": 0x47,
    "numpad8": 0x48,
    "up": 0x48,
    "down": 0x50,
    "left": 0x4B,
    "right": 0x4D,
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
    "e": 0x45,
    "i": 0x49,
    "space": 0x20,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    # Hotkey for teleport (Ctrl+X); channel switching uses NumPad1..8
    "x": 0x58,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    # Numeric keypad virtual key codes
    "numpad1": 0x61,
    "numpad2": 0x62,
    "numpad3": 0x63,
    "numpad4": 0x64,
    "numpad5": 0x65,
    "numpad6": 0x66,
    "numpad7": 0x67,
    "numpad8": 0x68,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
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
        """Key press helper with optional window activity check.

        Parameters
        ----------
        dry : bool, default ``False``
            If ``True`` do not send real key events (test mode).
        active_fn : callable or None
            Zero‑argument function returning ``True`` when the window is
            active. When ``False`` the watchdog releases all keys.

        PL:
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
        key = key.lower()
        if key in SCANCODES:
            scan = SCANCODES[key]
            extended = key in EXTENDED_KEYS
            if extended:
                key_down(scan, extended=True)
            else:
                key_down(scan)
        elif pydirectinput is not None:
            pydirectinput.keyDown(key, _pause=False)

    def _up(self, key: str) -> None:
        if self.dry or (self.active_fn is not None and not self.active_fn()):
            return
        key = key.lower()
        if key in SCANCODES:
            scan = SCANCODES[key]
            extended = key in EXTENDED_KEYS
            if extended:
                key_up(scan, extended=True)
            else:
                key_up(scan)
        elif pydirectinput is not None:
            pydirectinput.keyUp(key, _pause=False)

    def press(self, key: str):
        key = key.lower()
        with self.lock:
            if key not in self.down:
                logger.debug("Naciśnięto klawisz %s", key)
                self._down(key)
                self.down.add(key)

    def release(self, key: str):
        key = key.lower()
        with self.lock:
            if key in self.down:
                logger.debug("Zwolniono klawisz %s", key)
                self._up(key)
                self.down.remove(key)

    def tap(self, key: str, duration: float = 0.05) -> None:
        """Press and release ``key`` after ``duration`` seconds.

        This convenience wrapper depends on :mod:`pydirectinput` to emit the
        keyboard events by delegating to :meth:`press` and :meth:`release`.
        """

        self.press(key)
        time.sleep(duration)
        self.release(key)

    def hotkey(self, keys: list[str], duration: float = 0.05) -> None:
        """Press ``keys`` together and hold for ``duration`` seconds.

        Keys are pressed in the provided order and released in reverse order
        after a short sleep so that the combination is reliably registered.
        """

        for k in keys:
            self.press(k)
        time.sleep(duration)
        for k in reversed(keys):
            self.release(k)

    def release_all(self):
        with self.lock:
            if self.down:
                logger.debug("Zwolniono wszystkie klawisze: %s", list(self.down))
            for k in list(self.down):
                self._up(k)
            self.down.clear()
