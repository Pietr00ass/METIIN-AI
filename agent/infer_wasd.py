from __future__ import annotations

import time

import numpy as np

from recorder.window_capture import WindowCapture

from . import AgentConfig, TeleportSlot
from .strategy import load_strategy


class WasdVisionAgent:
    def __init__(self, cfg: AgentConfig | dict):
        """Create a vision agent using ``cfg`` configuration."""

        if isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.channels = list(cfg.channels)
        self.teleport_slots = list(cfg.teleport.slots)
        self.win = WindowCapture(cfg.window.title_substr)
        self.period = 1 / 15
        self.hd = None

    # ------------------------------------------------------------------
    # Public mutators allowing user customisation
    # ------------------------------------------------------------------
    def set_channels(self, channels: list[int]) -> None:
        """Replace the channel list used by the agent."""

        self.channels = list(channels)
        self.cfg.channels = list(channels)

    def set_teleport_slots(self, slots: list[TeleportSlot]) -> None:
        """Replace the teleport slot definitions."""

        self.teleport_slots = list(slots)
        self.cfg.teleport.slots = list(slots)

    def run(self):
        try:
            if not self.win.locate(timeout=5):
                raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")
            self.hd = load_strategy(self.cfg, self.win)
            while True:
                self.hd.step()
                time.sleep(self.period)
        except KeyboardInterrupt:
            if self.hd:
                try:
                    self.hd.teleporter.close_panel()
                except Exception:
                    pass
                try:
                    self.hd.keys.release_all()
                except Exception:
                    pass
        finally:
            self.win.close()
