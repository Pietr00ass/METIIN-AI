from __future__ import annotations
import time
import numpy as np
from recorder.window_capture import WindowCapture
from .hunt_destroy import HuntDestroy

class WasdVisionAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.win = WindowCapture(cfg['window']['title_substr'])
        self.period = 1 / 15
        self.hd = None

    def run(self):
        if not self.win.locate(timeout=5):
            raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")
        self.hd = HuntDestroy(self.cfg, self.win)
        while True:
            self.hd.step()
            time.sleep(self.period)
