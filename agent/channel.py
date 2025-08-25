from __future__ import annotations
import time
import numpy as np
import pyautogui
from recorder.window_capture import WindowCapture
from .template_matcher import TemplateMatcher


class ChannelSwitcher:
"""
Kliknięcie CH1..CH8 na minimapie w prawym górnym rogu.
Wymaga szablonów: assets/templates/ch1.png ... ch8.png
"""
def __init__(self, win: WindowCapture, templates_dir="assets/templates", dry: bool=False):
self.win = win
self.tm = TemplateMatcher(templates_dir)
self.dry = dry


def _frame(self):
fr = self.win.grab()
return np.array(fr)[:, :, :3].copy()


def switch(self, ch: int, thresh=0.82, tries=3):
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
self.win.focus()
if not self.dry:
pyautogui.moveTo(L + cx, T + cy, duration=0.05)
pyautogui.click()
time.sleep(0.3)
return True
time.sleep(0.2)
return False