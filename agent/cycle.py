from __future__ import annotations

import numpy as np

from recorder.window_capture import WindowCapture
from agent.teleport import Teleporter
from agent.channel import ChannelSwitcher
from agent.hunt_destroy import HuntDestroy
from agent.detector import ObjectDetector
from agent.wasd import KeyHold


class CycleFarm:
    """
    Cykl 8×8: sloty 1..8 × CH(ch_from..ch_to).
    Na każdym slocie: teleport -> poluj (z autoskanem 'E').
    Brak celu -> krótki skan E; nadal brak -> kolejny slot.
    Ma cooldown slotów (minuty) by nie wracać od razu.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.win = WindowCapture(cfg["window"]["title_substr"])
        assert self.win.locate()

        self.dry = cfg.get("dry_run", False)
        self.tp = Teleporter(self.win, use_ocr=True, dry=self.dry)
        self.ch = ChannelSwitcher(self.win, dry=self.dry)
        self.agent = HuntDestroy(cfg, self.win)
        self.det = ObjectDetector(cfg["detector"]["model_path"], cfg["detector"]["classes"])
        self.keys = KeyHold(dry=self.dry, active_fn=getattr(self.win, "is_foreground", None))
        self._stop = False

        # progi i priorytety
        self.conf_thr = float(cfg.get("detector", {}).get("conf_thr", 0.5))
        self.priority = list(cfg.get("priority", []))

        # parametry skanowania
        scan = cfg.get("scan", {})
        self.spin_key = scan.get("key", "e")
        self.sweep_ms = int(scan.get("sweep_ms", 250))
        self.sweeps = int(scan.get("sweeps", 8))
        self.idle_before_scan = float(scan.get("idle_sec", 1.5))
        self.pause_between_sweeps = float(scan.get("pause", 0.12))

        # cooldown slotów
        self.cooldown = {}
        self.cooldown_min = int(cfg.get("cooldowns", {}).get("slot_min", 10))

    def stop(self):
        self._stop = True
        try:
            self.keys.stop()
        except Exception:
            pass

    # ---- detekcje ----
    def _any_target_seen(self) -> bool:
        fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()
        dets = self.det.infer(frame)
        return bool(dets)
