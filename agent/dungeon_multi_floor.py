from __future__ import annotations

import logging
from typing import Any

import numpy as np

from . import AgentConfig, get_config
from .detector import ObjectDetector
from .dungeon_fsm import DungeonFSM
from .message_parser import parse_message
from .strategy import AgentStrategy, register
from .teleport import Teleporter
from .wasd import KeyHold
from .game_controller import controller
from . import vision

logger = logging.getLogger(__name__)


@register("dungeon_multi_floor")
class DungeonMultiFloor(AgentStrategy):
    """Strategy that moves through a multi-floor dungeon using an FSM."""

    def __init__(self, cfg: AgentConfig | dict | None = None, window_capture: Any | None = None):
        self.cfg: AgentConfig | None = None
        self.win = None
        self.det: ObjectDetector | None = None
        self.teleporter: Teleporter | None = None
        self.keys: KeyHold | None = None
        self.fsm: DungeonFSM | None = None
        if cfg is not None or window_capture is not None:
            self.setup(cfg, window_capture)

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
            cv2_threads=getattr(cfg.detector, "cv2_threads", None),
        )
        dry = cfg.dry_run
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg.paths.templates_dir
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)
        self.fsm = DungeonFSM(cfg.dungeon_fsm)

    def step(self) -> None:
        frame = np.array(self.win.grab())[:, :, :3].copy()
        if vision.is_logged_out(frame):
            if controller is not None:
                try:
                    controller.restart_game()
                except Exception:  # pragma: no cover - defensive
                    logger.warning("restart_game failed", exc_info=True)
            return
        if vision.is_loading(frame):
            if controller is not None:
                try:
                    controller.ensure_logged_in()
                except Exception:  # pragma: no cover - defensive
                    logger.warning("ensure_logged_in failed", exc_info=True)
            return
        _, event = parse_message(frame)
        detections = self.det.infer(frame) if self.det else []
        transition = self.fsm.update(event, detections) if self.fsm else None
        if transition:
            logger.info(
                "Dungeon transition %s -> %s (%s)",
                transition.from_state,
                transition.to_state,
                transition.reason,
            )
            if transition.to_state == "reset":
                self._handle_reset()

    def _handle_reset(self) -> None:
        if self.keys:
            self.keys.release_all()
        if not self.teleporter or not self.cfg:
            return
        slot = self.cfg.teleport.slots[0].slot if self.cfg.teleport.slots else 1
        try:
            self.teleporter.teleport_slot(slot)
        except Exception:  # pragma: no cover - defensive
            logger.warning("Teleportation failed", exc_info=True)

    def stop(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            if self.keys:
                self.keys.stop()
        except Exception:
            pass


__all__ = ["DungeonMultiFloor"]
