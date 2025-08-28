from __future__ import annotations

import os
import time
from typing import Callable, Optional, Tuple

import numpy as np
import pyautogui

from recorder.window_capture import WindowCapture

from .template_matcher import TemplateMatcher


class ChannelSwitcher:
    """Utility for clicking CH1..CH8 buttons on the in‑game minimap.

    The implementation relies on template images ``ch1.png`` … ``ch8.png``
    stored within ``templates_dir``.  Channels are switched by locating the
    corresponding template on the minimap and clicking it.  A dry mode can be
    enabled which skips the actual mouse interaction for testing purposes.
    """

    def __init__(self, win: WindowCapture, templates_dir: str, dry: bool = False):
        self.win = win
        if not os.path.isdir(templates_dir):
            raise FileNotFoundError(
                f"Brak katalogu z szablonami: {templates_dir}"
            )
        required = [f"ch{i}.png" for i in range(1, 9)]
        missing = [
            p for p in required if not os.path.isfile(os.path.join(templates_dir, p))
        ]
        if missing:
            raise FileNotFoundError(
                f"Brak plików w {templates_dir}: {', '.join(missing)}"
            )
        self.tm = TemplateMatcher(templates_dir)
        self.dry = dry

    # ------------------------------------------------------------------
    # Frame helpers
    def _frame(self) -> np.ndarray:
        """Return the current game frame as an RGB numpy array."""

        fr = self.win.grab()
        return np.array(fr)[:, :, :3].copy()

    def _minimap_roi(self) -> Tuple[int, int, int, int]:
        """Region of interest containing the minimap in the top‑right corner."""

        _, _, w, h = self.win.region
        return max(0, w - 260), 20, 240, 240

    # ------------------------------------------------------------------
    # Low level helpers
    def find_button(
        self,
        frame: np.ndarray,
        ch: int,
        thresh: float = 0.82,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ):
        """Find channel button ``ch`` within ``frame``.

        Returns matcher result or ``None`` if not found.
        """

        if roi is None:
            roi = self._minimap_roi()
        name = f"ch{ch}"
        return self.tm.find(frame, name, thresh=thresh, roi=roi, multi_scale=True)

    def color_at(
        self, x: int, y: int, frame: Optional[np.ndarray] = None
    ) -> Tuple[int, int, int]:
        """Return RGB colour at coordinates relative to the minimap ROI."""

        if frame is None:
            frame = self._frame()
        rx, ry, _, _ = self._minimap_roi()
        px = rx + int(x)
        py = ry + int(y)
        r, g, b = frame[py, px]
        return int(r), int(g), int(b)

    @staticmethod
    def is_gold(color: Tuple[int, int, int]) -> bool:
        """Heuristic check whether ``color`` resembles the gold selection colour."""

        r, g, b = color
        return r > 200 and g > 170 and b < 80

    # ------------------------------------------------------------------
    # Channel operations
    def switch(
        self,
        ch: int,
        thresh: float = 0.82,
        tries: int = 3,
        post_wait: float = 5.0,
    ) -> bool:
        """Attempt to switch to channel ``ch``.

        The window is focused before clicking.  In dry mode no mouse actions are
        performed.  ``post_wait`` seconds are waited after a successful click to
        allow the game to perform the switch.
        """

        if not (1 <= ch <= 8):
            raise ValueError("Kanał poza zakresem 1..8")

        roi = self._minimap_roi()
        for _ in range(tries):
            frame = self._frame()
            m = self.find_button(frame, ch, thresh=thresh, roi=roi)
            if m:
                L, T, _, _ = self.win.region
                cx, cy = m["center"]

                # Ensure the game window is focused before clicking.
                if hasattr(self.win, "focus"):
                    self.win.focus()
                if hasattr(self.win, "is_foreground") and not self.win.is_foreground():
                    time.sleep(0.1)
                    if hasattr(self.win, "focus"):
                        self.win.focus()
                    if hasattr(self.win, "is_foreground") and not self.win.is_foreground():
                        return False

                if not self.dry:
                    pyautogui.moveTo(L + cx, T + cy, duration=0.05)
                    pyautogui.click()
                if post_wait:
                    time.sleep(post_wait)
                return True
            time.sleep(0.2)
        return False

    def current_channel_guess(self, thresh: float = 0.82) -> Optional[int]:
        """Guess currently selected channel by looking for gold buttons."""

        frame = self._frame()
        roi = self._minimap_roi()
        for ch in range(1, 9):
            m = self.find_button(frame, ch, thresh=thresh, roi=roi)
            if m:
                cx, cy = m["center"]
                color = self.color_at(cx, cy, frame)
                if self.is_gold(color):
                    return ch
        return None

    @staticmethod
    def next(ch: int) -> int:
        """Return the next channel number, cycling 8 → 1."""

        if not (1 <= ch <= 8):
            raise ValueError("Kanał poza zakresem 1..8")
        return 1 if ch == 8 else ch + 1

    def cycle_until_target_seen(
        self,
        check_fn: Callable[[], bool],
        timeout: float = 30.0,
        post_wait: float = 5.0,
    ) -> bool:
        """Cycle through channels until ``check_fn`` returns ``True`` or timeout.

        ``check_fn`` should perform whatever check is required to detect the
        desired target (for example, running an object detector).  Channels are
        switched in order CH1→CH8 and wrap back to CH1.
        """

        start = time.time()
        current = self.current_channel_guess() or 1

        if check_fn():
            return True

        while time.time() - start < timeout:
            current = self.next(current)
            self.switch(current, post_wait=post_wait)
            if check_fn():
                return True
        return False

