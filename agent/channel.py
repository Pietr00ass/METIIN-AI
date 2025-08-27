from __future__ import annotations
import time
import os
import numpy as np
import pyautogui
from recorder.window_capture import WindowCapture
from .template_matcher import TemplateMatcher


class ChannelSwitcher:
    """
    Kliknięcie CH1..CH8 na minimapie w prawym górnym rogu.
    Wymaga szablonów: assets/templates/ch1.png ... ch8.png
    """

    def __init__(self, win: WindowCapture, templates_dir: str, dry: bool = False):
        self.win = win
        if not os.path.isdir(templates_dir):
            raise FileNotFoundError(f"Brak katalogu z szablonami: {templates_dir}")
        required = [f"ch{i}.png" for i in range(1, 9)]
        missing = [p for p in required if not os.path.isfile(os.path.join(templates_dir, p))]
        if missing:
            raise FileNotFoundError(f"Brak plików w {templates_dir}: {', '.join(missing)}")
        self.tm = TemplateMatcher(templates_dir)
        self.dry = dry

    def _frame(self) -> np.ndarray:
        fr = self.win.grab()
        return np.array(fr)[:, :, :3].copy()

    def switch(self, ch: int, thresh: float = 0.82, tries: int = 3) -> bool:
        if not (1 <= ch <= 8):
            raise ValueError("Kanał poza zakresem 1..8")
        # ROI: obszar minimapy ~ prawy górny róg okna
        _, _, w, h = self.win.region
        roi = (max(0, w - 260), 20, 240, 240)
        name = f"ch{ch}"

        for _ in range(tries):
            frame = self._frame()
            m = self.tm.find(frame, name, thresh=thresh, roi=roi, multi_scale=True)
            if m:
                L, T, _, _ = self.win.region
                cx, cy = m["center"]

                if not self.win.is_foreground():
                    self.win.focus()
                    if not self.win.is_foreground():
                        return False

                if not self.dry:
                    pyautogui.moveTo(L + cx, T + cy, duration=0.05)
                    pyautogui.click()
                time.sleep(0.3)
                return True
            time.sleep(0.2)
        return False
