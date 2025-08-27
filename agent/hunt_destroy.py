from __future__ import annotations
import time
import logging
import numpy as np

from .detector import ObjectDetector
from .targets import pick_target
from .avoid import CollisionAvoid
from .wasd import KeyHold
from .interaction import burst_click
from .teleport import Teleporter
from .channel import ChannelSwitcher


logger = logging.getLogger(__name__)


class HuntDestroy:
    def __init__(self, cfg, window_capture):
        self.win = window_capture
        self.det = ObjectDetector(
            cfg["detector"]["model_path"],
            cfg["detector"]["classes"],
            cfg["detector"]["conf_thr"],
            cfg["detector"]["iou_thr"],
        )
        self.avoid = CollisionAvoid()
        # KeyHold z dry-run + watchdogiem fokusu
        dry = cfg.get("dry_run", False)
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg["templates_dir"]
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry)
        self.channel_switcher = ChannelSwitcher(self.win, tdir, dry=dry)
        self.desired_w = cfg["policy"]["desired_box_w"]
        self.deadzone = cfg["policy"]["deadzone_x"]
        self.priority = cfg.get("priority", ["boss", "metin", "potwory"])  # kolejność z GUI
        self.period = 1 / 15
        self.last_target_time = time.time()
        self.location_idx = 0
        self.channel_idx = 0
        tp_cfg = cfg.get("teleport", {})
        self.tp_slots = list(tp_cfg.get("slots", []))
        self.tp_page = tp_cfg.get("page") or tp_cfg.get("page_label")
        self.channels = list(cfg.get("channels", []))
        self._teleports = 0
        self._last_tgt = None
        self._prev_names: set[str] = set()

    def step(self):
        fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()
        H, W = frame.shape[:2]
        dets = self.det.infer(frame)
        logger.debug("Wykryto %s obiektów", len(dets))
        cur_names = {d["name"] for d in dets}
        disappeared = self._prev_names - cur_names
        for name in disappeared:
            logger.debug("Obiekt %s zniknął", name)
        self._prev_names = cur_names
        steer = self.avoid.steer(frame)

        # sterowanie
        self.keys.release_all()
        if steer == "left":
            logger.debug("Omijanie przeszkody: skręt w lewo")
            self.keys.press("a")
        elif steer == "right":
            logger.debug("Omijanie przeszkody: skręt w prawo")
            self.keys.press("d")

        tgt = pick_target(dets, (W, H), priority_order=self.priority)
        if tgt is None and self._last_tgt is not None:
            logger.debug("Cel %s zniknął", self._last_tgt.get("name", "?"))
        if tgt is None:
            logger.debug("Brak celu w zasięgu")
            now = time.time()
            if now - self.last_target_time > 10:
                slot = None
                try:
                    if self.tp_slots:
                        slot = self.tp_slots[self.location_idx % len(self.tp_slots)]
                        self.teleporter.teleport_slot(slot, self.tp_page)
                        self._teleports += 1
                        self.location_idx = (self.location_idx + 1) % len(self.tp_slots)
                        if self._teleports % 8 == 0 or self.location_idx == 0:
                            if self.channels:
                                ch = self.channels[self.channel_idx % len(self.channels)]
                                try:
                                    self.channel_switcher.switch(ch)
                                except Exception:
                                    logger.warning("Nie udało się zmienić kanału na %s", ch)
                                self.channel_idx = (self.channel_idx + 1) % len(self.channels)
                    else:
                        logger.debug("Lista slotów teleportu jest pusta")
                except Exception:
                    logger.warning("Teleportacja na slot %s nie powiodła się", slot)
                self.last_target_time = now
            self._last_tgt = tgt
            return

        x1, y1, x2, y2 = tgt["bbox"]
        cx = (x1 + x2) / 2 / W
        bw = (x2 - x1) / W
        logger.debug(
            "Cel %s: cx=%.2f bw=%.2f", tgt.get("name", "?"), cx, bw
        )
        self.last_target_time = time.time()
        self._last_tgt = tgt

        if abs(cx - 0.5) > self.deadzone:
            (self.keys.press("d") if cx > 0.5 else self.keys.press("a"))
        if bw < self.desired_w * 0.95:
            self.keys.press("w")
        elif bw > self.desired_w * 1.25:
            self.keys.press("s")

        if bw >= self.desired_w * 0.9:
            left, top, w, h = self.win.region
            # w dry-run nie klikamy realnie – burst_click sam używa pyautogui
            if hasattr(self.keys, "dry") and self.keys.dry:
                return
            logger.debug("Atakuję cel" )
            burst_click((x1, y1, x2, y2), (left, top, w, h))
