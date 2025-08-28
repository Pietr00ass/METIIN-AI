from __future__ import annotations

import logging
import time

import numpy as np

from . import get_config
from .avoid import CollisionAvoid
from .channel import ChannelSwitcher
from .detector import ObjectDetector
from .interaction import click_bbox_center
from .movement import MovementController
from .search import SearchManager
from .targets import pick_target
from .teleport import Teleporter
from .wasd import KeyHold

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
        dry = cfg.get("dry_run", False)
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg["paths"]["templates_dir"]
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)
        self.channel_switcher = ChannelSwitcher(self.win, tdir, dry=dry, keys=self.keys)
        self.desired_w = cfg["policy"].get("desired_box_w", 0.12)
        self.deadzone = cfg["policy"].get("deadzone_x", 0.05)
        self.priority = cfg.get("priority", ["boss", "metin", "potwory"])
        self.period = cfg.get("scan", {}).get("period", 1 / 15)

        tp_cfg = cfg.get("teleport", {})
        self.search = SearchManager(
            self.teleporter,
            self.channel_switcher,
            list(tp_cfg.get("slots", [])),
            tp_cfg.get("page") or tp_cfg.get("page_label"),
            list(cfg.get("channels", [])),
            tp_cfg.get("no_target_sec", 10),
            tp_cfg.get("channel_every", 8),
        )
        self.movement = MovementController(self.keys, self.desired_w, self.deadzone)
        self._last_tgt = None
        self._prev_names: set[str] = set()
        self._spin_start: float | None = None
        self._spin_dir = "a"

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
        tgt = pick_target(dets, (W, H), priority_order=self.priority)
        if tgt is None and self._last_tgt is not None:
            logger.debug("Cel %s zniknął", self._last_tgt.get("name", "?"))
        if tgt is None:
            logger.debug("Brak celu w zasięgu")
            now = time.time()
            if self._spin_start is None:
                self._spin_start = now
                self.keys.press(self._spin_dir)
            elif now - self._spin_start >= 4:
                self.keys.release(self._spin_dir)
                self._spin_start = None
                self._spin_dir = "d" if self._spin_dir == "a" else "a"
                self.search.handle_no_target()
            self._last_tgt = None
            return

        if self._spin_start is not None:
            self.keys.release(self._spin_dir)
            self._spin_start = None
        self.search.update_last_target()

        bw = None
        if tgt:
            x1, y1, x2, y2 = tgt["bbox"]
            bw = (x2 - x1) / W

        if tgt and bw is not None and bw >= self.desired_w * 0.9:
            self.keys.release_all()
            left, top, w, h = self.win.region
            if hasattr(self.keys, "dry") and self.keys.dry:
                return
            logger.debug("Atakuję cel")
            click_bbox_center(tgt["bbox"], (left, top, w, h), win=self.win)
        else:
            self.movement.move(tgt, steer, (W, H))
        self._last_tgt = tgt
