from __future__ import annotations
import time
import mss
import pygetwindow as gw

class WindowCapture:
    """Przechwytuje konkretnie wybrane okno po fragmencie tytułu."""
    def __init__(self, title_substr: str, poll_sec=0.5):
        self.title_substr = title_substr
        self.poll_sec = poll_sec
        self.win = None
        self.region = None  # (left, top, width, height)
        self.sct = mss.mss()

    def locate(self) -> bool:
        while True:
            wins = [w for w in gw.getAllWindows() if self.title_substr.lower() in w.title.lower()]
            wins = [w for w in wins if w.isVisible]
            if wins:
                self.win = wins[0]
                self.update_region()
                return True
            time.sleep(self.poll_sec)

    def update_region(self):
        self.win.activate(); time.sleep(0.05)
        self.region = (self.win.left, self.win.top, self.win.width, self.win.height)

    def grab(self):
        if self.region is None:
            self.update_region()
        left, top, width, height = self.region
        return self.sct.grab({'left': left, 'top': top, 'width': width, 'height': height})
