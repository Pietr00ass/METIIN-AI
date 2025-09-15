from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from . import AgentConfig, get_config
from .detector import ObjectDetector
from .message_parser import parse_message
from .strategy import AgentStrategy, register
from .teleport import Teleporter
from .wasd import KeyHold

logger = logging.getLogger(__name__)


@register("dungeon_polana")
class DungeonPolana(AgentStrategy):
    """Strategy handling the Polana dungeon flow.

    The sequence is simple:

    * search for the boss using the object detector,
    * periodically use the configured teleport slot when no boss is found,
    * watch for in‑game error messages ("no boss", "dungeon finished", etc.).
    """

    def __init__(self, cfg: AgentConfig | dict | None = None, window_capture: Any | None = None):
        self.cfg: AgentConfig | None = None
        self.win = None
        self.det: ObjectDetector | None = None
        self.teleporter: Teleporter | None = None
        self.keys: KeyHold | None = None
        self.tp_slot: int = 1
        self.boss_timeout: float = 30.0
        self.error_timeout: float = 5.0
        self.last_boss_time: float = 0.0
        self.last_event: str | None = None
        if cfg is not None or window_capture is not None:
            self.setup(cfg, window_capture)

    # ------------------------------------------------------------------ setup
    def setup(self, cfg: AgentConfig | dict | None = None, window_capture: Any | None = None) -> None:
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
            cv2_threads=cfg.detector.cv2_threads,
        )
        dry = cfg.dry_run
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg.paths.templates_dir
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)

        dp_cfg = cfg.dungeon_polana
        self.tp_slot = int(dp_cfg.teleport_slot)
        self.boss_timeout = float(dp_cfg.boss_timeout)
        self.error_timeout = float(dp_cfg.error_timeout)
        self.last_boss_time = time.monotonic()
        self.last_event = None

    # ------------------------------------------------------------------- logic
    def step(self) -> None:
        fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()

        # check for overlay messages first
        _, event = parse_message(frame)
        if event:
            logger.info("Detected message: %s", event)
            self.last_event = event
            if self.keys:
                self.keys.release_all()
            try:  # teleport away to reset the dungeon
                self.teleporter.teleport_slot(self.tp_slot)
            except Exception:  # pragma: no cover - defensive
                logger.warning("Teleportation failed", exc_info=True)
            self.last_boss_time = time.monotonic() + self.error_timeout
            return

        dets = self.det.infer(frame)
        boss = next((d for d in dets if d.name == "boss"), None)
        if boss:
            logger.debug("Boss detected")
            self.last_boss_time = time.monotonic()
            return

        now = time.monotonic()
        if now - self.last_boss_time > self.boss_timeout:
            logger.info("No boss detected – using teleport slot %s", self.tp_slot)
            try:
                self.teleporter.teleport_slot(self.tp_slot)
            except Exception:  # pragma: no cover - defensive
                logger.warning("Teleportation failed", exc_info=True)
            self.last_boss_time = now

    # -------------------------------------------------------------------- stop
    def stop(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            if self.keys:
                self.keys.stop()
        except Exception:
            pass
