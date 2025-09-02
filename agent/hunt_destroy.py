from __future__ import annotations

import logging

import numpy as np

from . import AgentConfig, get_config
from .avoid import CollisionAvoid
from .channel import ChannelSwitcher
from .detector import ObjectDetector
from .interaction import click_bbox_center
from .movement import MovementController
from .scanner import AreaScanner
from .search import SearchManager
from .strategy import AgentStrategy, register
from .targets import pick_target
from .teleport import Teleporter
from .wasd import KeyHold

logger = logging.getLogger(__name__)


@register("hunt_destroy")
class HuntDestroy(AgentStrategy):
    def __init__(self, cfg=None, window_capture=None):
        self.cfg = None
        self.win = None
        self.det = None
        self.avoid = None
        self.keys = None
        self.teleporter = None
        self.channel_switcher = None
        self.desired_w = 0.0
        self.deadzone = 0.0
        self.priority = []
        self.period = 0.0
        self.scanner = None
        self.search = None
        self.movement = None
        self._last_tgt = None
        self._prev_names: set[str] = set()
        if cfg is not None or window_capture is not None:
            self.setup(cfg, window_capture)

    def setup(self, cfg: AgentConfig | dict | None = None, window_capture=None):
        if cfg is None:
            cfg = get_config()
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.win = window_capture
        self.det = ObjectDetector(
            cfg.paths.model,
            cfg.detector.classes,
            cfg.detector.conf_thr,
            cfg.detector.iou_thr,
        )
        self.avoid = CollisionAvoid()
        dry = cfg.dry_run
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg.paths.templates_dir
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)
        ch_hotkeys = cfg.channel.hotkeys
        self.channel_switcher = ChannelSwitcher(
            self.win, tdir, dry=dry, keys=self.keys, hotkeys=ch_hotkeys
        )
        self.desired_w = float(cfg.detector.policy.desired_box_w)
        self.deadzone = float(cfg.detector.policy.deadzone_x)
        self.priority = list(cfg.priority)
        scan_cfg = cfg.scan
        self.period = scan_cfg.period
        self.scanner = None
        if scan_cfg.enabled:
            rot_key = cfg.controls.keys.rotate or cfg.controls.keys.left
            self.scanner = AreaScanner(
                self.keys,
                spin_key=rot_key,
                sweep_ms=scan_cfg.sweep_ms,
                sweeps=scan_cfg.sweeps,
                idle_sec=scan_cfg.idle_sec,
                pause=scan_cfg.pause,
            )

        tp_cfg = cfg.teleport
        self.search = SearchManager(
            self.teleporter,
            self.channel_switcher,
            [s.slot for s in tp_cfg.slots],
            tp_cfg.page or tp_cfg.page_label,
            list(cfg.channels),
            tp_cfg.no_target_sec,
            tp_cfg.channel_every,
        )
        move_enabled = cfg.controls.movement
        self.movement = MovementController(
            self.keys, self.desired_w, self.deadzone, enabled=move_enabled
        )
        self._last_tgt = None
        self._prev_names = set()

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
            if self.scanner:
                self.scanner.scan()
                self.search.handle_no_target(True)
                self._last_tgt = None
                return
            self._last_tgt = None
            return

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
