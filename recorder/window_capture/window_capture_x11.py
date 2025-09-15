from __future__ import annotations

import subprocess
import time
import types

import mss
try:  # pragma: no cover - pygetwindow unsupported on Linux
    import pygetwindow as gw
except Exception:  # ImportError or NotImplementedError
    gw = types.SimpleNamespace(
        getAllWindows=lambda: (_ for _ in ()).throw(NotImplementedError)
    )


def _wmctrl_windows() -> list[types.SimpleNamespace]:
    """Return a list of window-like objects using the ``wmctrl`` command.

    The returned objects mimic the subset of the ``pygetwindow.Window`` API used
    by :class:`WindowCapture` (``title``, ``left``, ``top``, ``width``,
    ``height``, ``restore`` and ``activate`` methods).
    """

    try:
        out = subprocess.run(
            ["wmctrl", "-lpG"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except Exception:
        return []

    wins: list[types.SimpleNamespace] = []
    for line in out:
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        wid, _desk, _pid, x, y, w, h, title = parts

        def _activate(win_id=wid):
            try:
                subprocess.run(
                    ["wmctrl", "-i", "-a", win_id], capture_output=True
                )
            except Exception:
                pass

        wins.append(
            types.SimpleNamespace(
                wid=wid,
                title=title.strip(),
                left=int(x),
                top=int(y),
                width=int(w),
                height=int(h),
                isMinimized=False,
                restore=lambda: None,
                activate=_activate,
            )
        )
    return wins


class WindowCapture:
    """Przechwytuje wskazane okno po fragmencie tytułu + helpery focus/foreground."""

    def __init__(self, title_substr: str, poll_sec: float = 0.5):
        self.title_substr = title_substr
        self.poll_sec = poll_sec
        self.win = None  # pygetwindow.Window
        self.region = None  # (left, top, width, height)
        self.sct = mss.mss()

    def close(self) -> None:
        """Release underlying screenshot resources."""
        try:
            self.sct.close()
        except Exception:
            pass

    # -----------------------------------------------------
    # Context manager API
    def __enter__(self) -> "WindowCapture":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

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
            wins: list[types.SimpleNamespace]
            try:
                wins = [
                    w for w in gw.getAllWindows() if needle in (w.title or "").lower()
                ]
            except Exception:
                wins = [
                    w for w in _wmctrl_windows() if needle in (w.title or "").lower()
                ]
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
        if hasattr(self.win, "wid"):
            # Refresh geometry for wmctrl fallback windows
            for w in _wmctrl_windows():
                if w.wid == self.win.wid:
                    self.win.left, self.win.top = w.left, w.top
                    self.win.width, self.win.height = w.width, w.height
                    break
        left, top = int(self.win.left), int(self.win.top)
        width, height = int(self.win.width), int(self.win.height)
        if width <= 0 or height <= 0:
            width, height = 1280, 720
        self.region = (left, top, width, height)

    # --- Focus / foreground helpers ---
    def hwnd(self):
        """Not available on X11."""
        return None

    def is_foreground(self) -> bool:
        """Foreground checks are not supported on X11."""
        return False

    def focus(self) -> bool:
        """Attempting to focus is not supported on X11."""
        return False

    def grab(self, update_region: bool = False):
        """Zwraca mss.base.ScreenShot (BGRA)."""
        if update_region or self.region is None:
            self.update_region()

        def _grab():
            left, top, width, height = self.region
            return self.sct.grab(
                {"left": left, "top": top, "width": width, "height": height}
            )

        img = _grab()
        if getattr(img, "width", 0) == 0 or getattr(img, "height", 0) == 0:
            self.update_region()
            img = _grab()
            if getattr(img, "width", 0) == 0 or getattr(img, "height", 0) == 0:
                raise RuntimeError(
                    "WindowCapture.grab captured empty image (zero width/height)"
                )
        return img
