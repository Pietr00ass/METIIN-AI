from __future__ import annotations

import time

import mss
import pygetwindow as gw
import win32con
import win32gui


class WindowCapture:
    """Przechwytuje wskazane okno po fragmencie tytułu + helpery focus/foreground."""

    def __init__(self, title_substr: str, poll_sec: float = 0.5):
        self.title_substr = title_substr
        self.poll_sec = poll_sec
        self.win = None  # pygetwindow.Window
        self.region = None  # (left, top, width, height)
        self.sct = mss.mss()

    def locate(self, timeout: float | None = None) -> bool:
        """Znajdź okno po fragmencie tytułu i ustaw region.

        Parameters
        ----------
        timeout: float | None
            Maksymalny czas oczekiwania w sekundach. ``None`` oznacza nieskończone
            oczekiwanie.

        Returns
        -------
        bool
            ``True`` jeśli okno zostało znalezione, ``False`` w przeciwnym razie.
        """
        needle = (self.title_substr or "").lower()
        start = time.time()
        attempts = 0
        while True:
            attempts += 1
            wins = [w for w in gw.getAllWindows() if needle in (w.title or "").lower()]
            if wins:
                w = wins[0]
                try:
                    if getattr(w, "isMinimized", False):
                        w.restore()
                    w.activate()
                except Exception:
                    pass
                self.win = w
                self.update_region()
                return True
            if timeout is not None and (time.time() - start) >= timeout:
                return False
            time.sleep(self.poll_sec)

    def update_region(self):
        """Odśwież left/top/width/height okna."""
        try:
            self.win.activate()
            time.sleep(0.05)
        except Exception:
            pass
        left, top = int(self.win.left), int(self.win.top)
        width, height = int(self.win.width), int(self.win.height)
        if width <= 0 or height <= 0:
            width, height = 1280, 720
        self.region = (left, top, width, height)

    # --- Focus / foreground helpers ---
    def hwnd(self):
        try:
            return int(self.win._hWnd)
        except Exception:
            return None

    def is_foreground(self) -> bool:
        h = self.hwnd()
        return bool(h and win32gui.GetForegroundWindow() == h)

    def focus(self) -> bool:
        h = self.hwnd()
        if not h:
            return False
        try:
            win32gui.ShowWindow(h, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(h)
            time.sleep(0.1)
            return True
        except Exception:
            return False

    def grab(self):
        """Zwraca mss.base.ScreenShot (BGRA)."""
        if self.region is None:
            self.update_region()
        left, top, width, height = self.region
        return self.sct.grab(
            {"left": left, "top": top, "width": width, "height": height}
        )
