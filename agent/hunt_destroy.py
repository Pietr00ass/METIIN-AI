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
from . import get_config


logger = logging.getLogger(__name__)


class HuntDestroy:
    def __init__(self, cfg=None, window_capture=None):
        cfg = cfg or get_config()
        self.cfg = cfg
        self.win = window_capture
        self.det = ObjectDetector(
            cfg["paths"]["model"],
            cfg["detector"]["classes"],
            cfg["detector"].get("conf_thr", 0.5),
            cfg["detector"].get("iou_thr", 0.45),
        )
        self.avoid = CollisionAvoid()
        # KeyHold z dry-run + watchdogiem fokusu
        dry = cfg.get("dry_run", False)
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg["paths"]["templates_dir"]
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)
        self.channel_switcher = ChannelSwitcher(self.win, tdir, dry=dry)
        self.desired_w = cfg["policy"].get("desired_box_w", 0.12)
        self.deadzone = cfg["policy"].get("deadzone_x", 0.05)
        self.priority = cfg.get("priority", ["boss", "metin", "potwory"])  # kolejność z GUI
        self.period = cfg.get("scan", {}).get("period", 1 / 15)
        self.last_target_time = time.time()
        self.location_idx = 0
        self.channel_idx = 0
        tp_cfg = cfg.get("teleport", {})
        self.tp_slots = list(tp_cfg.get("slots", []))
        self.tp_page = tp_cfg.get("page") or tp_cfg.get("page_label")
        self.channels = list(cfg.get("channels", []))
        self.no_target_sec = tp_cfg.get("no_target_sec", 10)
        self.channel_every = tp_cfg.get("channel_every", 8)
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

        desired_keys: set[str] = set()
        if steer == "left":
            logger.debug("Omijanie przeszkody: skręt w lewo")
            desired_keys.add("a")
        elif steer == "right":
            logger.debug("Omijanie przeszkody: skręt w prawo")
            desired_keys.add("d")

        tgt = pick_target(dets, (W, H), priority_order=self.priority)
        if tgt is None and self._last_tgt is not None:
            logger.debug("Cel %s zniknął", self._last_tgt.get("name", "?"))
        if tgt is None:
            logger.debug("Brak celu w zasięgu")
            now = time.time()
            if now - self.last_target_time > self.no_target_sec:
                slot = None
                try:
                    if self.tp_slots:
                        slot = self.tp_slots[self.location_idx % len(self.tp_slots)]
                        self.teleporter.teleport_slot(slot, self.tp_page)
                        self._teleports += 1
                        self.location_idx = (self.location_idx + 1) % len(self.tp_slots)
                        if self._teleports % self.channel_every == 0 or self.location_idx == 0:
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

            for k in self.keys.down - desired_keys:
                self.keys.release(k)
            for k in desired_keys - self.keys.down:
                self.keys.press(k)
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
            desired_keys.add("d" if cx > 0.5 else "a")
        if bw < self.desired_w * 0.95:
            desired_keys.add("w")
        elif bw > self.desired_w * 1.25:
            desired_keys.add("s")

        for k in self.keys.down - desired_keys:
            self.keys.release(k)
        for k in desired_keys - self.keys.down:
            self.keys.press(k)

        if bw >= self.desired_w * 0.9:
            left, top, w, h = self.win.region
            # w dry-run nie klikamy realnie – burst_click sam używa pyautogui
            if hasattr(self.keys, "dry") and self.keys.dry:
                return
            logger.debug("Atakuję cel")
            burst_click((x1, y1, x2, y2), (left, top, w, h))
