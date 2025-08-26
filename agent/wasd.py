from __future__ import annotations
import threading
import time
import win32api
import win32con

VK_CODES = {
    "w": ord("W"),
    "a": ord("A"),
    "s": ord("S"),
    "d": ord("D"),
    "shift": win32con.VK_SHIFT,
    "space": win32con.VK_SPACE,
    "ctrl": win32con.VK_CONTROL,
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
        self.hwnd = None
        if active_fn is not None:
            try:
                self.hwnd = getattr(active_fn.__self__, "hwnd", lambda: None)()
            except Exception:
                self.hwnd = None
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
                if not self.dry and self.hwnd:
                    win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, VK_CODES[key], 0)
                self.down.add(key)

    def release(self, key: str):
        with self.lock:
            if key in self.down:
                if not self.dry and self.hwnd:
                    win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_CODES[key], 0)
                self.down.remove(key)

    def release_all(self):
        with self.lock:
            if not self.dry and self.hwnd:
                for k in list(self.down):
                    win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, VK_CODES[k], 0)
            self.down.clear()
