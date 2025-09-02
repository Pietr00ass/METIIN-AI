from __future__ import annotations

import time

import cv2
import numpy as np
import torch
import torchvision.models as models

from recorder.window_capture import WindowCapture

from . import AgentConfig
from .model_kbd import KbdPolicy
from .stuck_flow import FlowStuck
from .wasd import KeyHold


class KbdVisionAgent:
    def __init__(self, cfg: AgentConfig | dict):
        if isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.win = WindowCapture(cfg.window.title_substr)
        self.keys = KeyHold()
        self.period = 1 / 15
        self.flow = FlowStuck(
            cfg.stuck.flow_window,
            fps=15,
            min_mag=cfg.stuck.min_flow_mag,
        )
        self.net = KbdPolicy(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        self.net.load_state_dict(
            torch.load("checkpoints/kbd_policy.pt", map_location="cpu")
        )
        self.net.eval()

    def run(self):
        try:
            if not self.win.locate(timeout=5):
                raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")
            while True:
                t0 = time.time()
                fr = self.win.grab()
                frame = np.array(fr)[:, :, :3]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                stuck = self.flow.update(gray)
                img = cv2.resize(frame, (224, 224))[:, :, ::-1]
                x = torch.tensor(img).permute(2, 0, 1).unsqueeze(0).float() / 255.0
                with torch.no_grad():
                    y = self.net(x).squeeze(0).numpy()
                self.keys.release_all()
                keys = ["w", "a", "s", "d"]
                for i, k in enumerate(keys):
                    if y[i] > 0.5:
                        self.keys.press(k)
                if stuck:
                    self.keys.release_all()
                    self.keys.press("a")
                    time.sleep(0.2)
                    self.keys.release_all()
                dt = time.time() - t0
                if dt < self.period:
                    time.sleep(self.period - dt)
        finally:
            self.win.close()
