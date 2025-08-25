from __future__ import annotations
import threading
import time
import pyautogui


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
                if not self.dry:
                    pyautogui.keyDown(key)
                self.down.add(key)

    def release(self, key: str):
        with self.lock:
            if key in self.down:
                if not self.dry:
                    pyautogui.keyUp(key)
                self.down.remove(key)

    def release_all(self):
        with self.lock:
            if not self.dry:
                for k in list(self.down):
                    pyautogui.keyUp(k)
            self.down.clear()
