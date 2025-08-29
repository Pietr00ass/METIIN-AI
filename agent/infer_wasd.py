from __future__ import annotations

import time

import numpy as np

from recorder.window_capture import WindowCapture

from . import AgentConfig, TeleportSlot
from .hunt_destroy import HuntDestroy


class WasdVisionAgent:
    def __init__(self, cfg):
        """Create a vision agent using ``cfg`` configuration.

        ``cfg`` may be either a raw configuration dictionary or an
        :class:`agent.AgentConfig` instance.  The teleport slots and channel
        list are parsed during initialisation so that the user may modify them
        later through :meth:`set_teleport_slots` and :meth:`set_channels`.
        """

        if isinstance(cfg, AgentConfig):
            self.channels = list(cfg.channels)
            self.teleport_slots = list(cfg.teleport_slots)
            cfg = cfg.data
        else:
            self.channels = list(cfg.get("channels", []))
            self.teleport_slots = [
                TeleportSlot(**s) for s in cfg.get("teleport", {}).get("slots", [])
            ]
        self.cfg = cfg
        self.win = WindowCapture(cfg["window"]["title_substr"])
        self.period = 1 / 15
        self.hd = None

    # ------------------------------------------------------------------
    # Public mutators allowing user customisation
    # ------------------------------------------------------------------
    def set_channels(self, channels: list[int]) -> None:
        """Replace the channel list used by the agent."""

        self.channels = list(channels)
        self.cfg["channels"] = list(channels)

    def set_teleport_slots(self, slots: list[TeleportSlot]) -> None:
        """Replace the teleport slot definitions."""

        self.teleport_slots = list(slots)
        self.cfg.setdefault("teleport", {})["slots"] = [s.__dict__ for s in slots]

    def run(self):
        try:
            if not self.win.locate(timeout=5):
                raise RuntimeError("Nie znaleziono okna – sprawdź title_substr")
            self.hd = HuntDestroy(self.cfg, self.win)
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
