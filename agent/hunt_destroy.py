from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from . import AgentConfig, get_config
from .avoid import CollisionAvoid
from .channel import ChannelSwitcher
from .detector import Detection, ObjectDetector
from .interaction import click_bbox_center
from .movement import MovementController
from . import minimap
from .message_parser import parse_message
from .scanner import AreaScanner
from .search import SearchManager
from .strategy import AgentStrategy, register
from .targets import pick_target
from .stuck_flow import FlowStuck
from .teleport import Teleporter
from .wasd import KeyHold
from .game_controller import controller
from .template_matcher import TemplateMatcher
from .loot import LootCollector
from .buff_manager import BuffManager
from . import potion_manager
from utils.logging_config import logger


@register("hunt_destroy")
class HuntDestroy(AgentStrategy):
    def __init__(self, cfg=None, window_capture=None, on_inventory_full=None, use_navigation: bool = False):
        self.cfg = None
        self.win = None
        self.det = None
        self.avoid = None
        self.keys = None
        self.teleporter = None
        self.channel_switcher = None
        self.matcher = None
        self.loot = None
        self.desired_w = 0.0
        self.deadzone = 0.0
        self.priority = []
        self.period = 0.0
        self.scanner = None
        self.search = None
        self.movement = None
        self.flow: FlowStuck | None = None
        self._recovery_action = "rotate"
        self._last_tgt: Detection | None = None
        self._prev_names: set[str] = set()
        self._grab_lock = threading.Lock()
        self.auto_press = None
        self._next_auto_press = 0.0
        self.buff_mgr: BuffManager | None = None
        self.on_inventory_full = on_inventory_full
        self.use_navigation = use_navigation
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
            cv2_threads=getattr(cfg.detector, "cv2_threads", 0),
        )
        self.avoid = CollisionAvoid()
        dry = cfg.dry_run
        self.keys = KeyHold(dry=dry, active_fn=getattr(self.win, "is_foreground", None))
        tdir = cfg.paths.templates_dir
        self.teleporter = Teleporter(self.win, tdir, use_ocr=True, dry=dry, cfg=cfg)
        self.matcher = TemplateMatcher(tdir)
        state = getattr(controller, "state", None)
        self.loot = LootCollector(
            detector=self.det,
            matcher=self.matcher,
            win=self.win,
            state=state,
        )
        ch_hotkeys = getattr(cfg.channel, "hotkeys", {})
        self.channel_switcher = ChannelSwitcher(
            self.win, tdir, dry=dry, keys=self.keys, hotkeys=ch_hotkeys
        )
        self.desired_w = float(cfg.detector.policy.desired_box_w)
        self.deadzone = float(cfg.detector.policy.deadzone_x)
        self.priority = list(cfg.priority)
        scan_cfg = cfg.scan
        self.period = scan_cfg.period
        self.scanner = None
        if getattr(scan_cfg, "enabled", True):
            rot_key = cfg.controls.keys.rotate or cfg.controls.keys.left
            self.scanner = AreaScanner(
                self.keys,
                spin_key=rot_key,
                sweep_ms=getattr(scan_cfg, "sweep_ms", 250),
                sweeps=getattr(scan_cfg, "sweeps", 8),
                idle_sec=getattr(scan_cfg, "idle_sec", 1.5),
                pause=getattr(scan_cfg, "pause", 0.12),
            )

        tp_cfg = cfg.teleport
        self.search = SearchManager(
            self.teleporter,
            self.channel_switcher,
            [s.slot for s in tp_cfg.slots],
            getattr(tp_cfg, "page", None) or getattr(tp_cfg, "page_label", None),
            list(cfg.channels),
            tp_cfg.no_target_sec,
            tp_cfg.channel_every,
        )
        move_enabled = cfg.controls.movement
        self.movement = MovementController(
            self.keys, self.desired_w, self.deadzone, enabled=move_enabled
        )
        self.auto_press = cfg.auto_press
        self._next_auto_press = time.monotonic() + cfg.auto_press.interval_sec
        self.buff_mgr = BuffManager.from_config(cfg, self.keys)
        self._last_tgt = None
        self._prev_names = set()
        fps = int(round(1 / self.period)) if self.period else 15
        self.flow = FlowStuck(cfg.stuck.window, fps=fps, min_mag=cfg.stuck.min_mag)
        self._recovery_action = cfg.stuck.recovery_action

    def step(self):
        ap_cfg = self.auto_press
        if ap_cfg and ap_cfg.enabled:
            now = time.monotonic()
            if now >= self._next_auto_press:
                self.keys.tap(ap_cfg.key)
                self._next_auto_press = now + ap_cfg.interval_sec
        if self.buff_mgr:
            self.buff_mgr.step()
        with self._grab_lock:
            fr = self.win.grab()
        frame = np.array(fr)[:, :, :3].copy()
        potion_manager.check_and_use(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.flow and self.flow.update(gray):
            self._recover_from_stuck()
            self.flow.reset()
            return
        _, event = parse_message(frame)
        if event:
            logger.info("Wykryto wiadomość: {}", event)
            if controller is not None:
                try:
                    controller.reset_state()
                except Exception:  # pragma: no cover - best effort
                    logger.opt(exception=True).warning("reset_state failed")
            if event in {"no boss", "dungeon finished"}:
                self.search.handle_no_target(True)
                self._last_tgt = None
                return
            if event == "death":
                self.keys.release_all()
                self._last_tgt = None
                return
            if event == "inventory full":
                self.keys.release_all()
                if self.on_inventory_full:
                    try:
                        self.on_inventory_full()
                    except Exception:  # pragma: no cover - defensive
                        logger.opt(exception=True).warning("inventory callback failed")
                else:
                    try:
                        slot = (
                            self.cfg.teleport.slots[0].slot
                            if self.cfg.teleport.slots
                            else 1
                        )
                        self.teleporter.teleport_slot(slot)
                    except Exception:  # pragma: no cover - defensive
                        logger.opt(exception=True).warning(
                            "Teleport on inventory full failed"
                        )
                self._last_tgt = None
                return
        H, W = frame.shape[:2]
        dets = self.det.infer(frame)
        logger.debug("Wykryto {} obiektów", len(dets))
        cur_names = {d.name for d in dets}
        disappeared = self._prev_names - cur_names
        for name in disappeared:
            logger.debug("Obiekt {} zniknął", name)
        if self._last_tgt and self._last_tgt.name in disappeared and self.loot:
            try:
                self.loot.collect(frame)
            except Exception:  # pragma: no cover - best effort
                logger.opt(exception=True).warning("loot collect failed")
        self._prev_names = cur_names

        steer = self.avoid.steer(frame)
        tgt = pick_target(dets, (W, H), priority_order=self.priority)
        if tgt is None and self._last_tgt is not None:
            logger.debug("Cel {} zniknął", self._last_tgt.name)
            if self.loot:
                try:
                    self.loot.collect(frame)
                except Exception:  # pragma: no cover - best effort
                    logger.opt(exception=True).warning("loot collect failed")
        if tgt is None:
            logger.debug("Brak celu w zasięgu")
            if self.scanner:
                if self.scanner.is_scanning():
                    self.search.handle_no_target(False)
                else:
                    if self.scanner.is_done():
                        self.search.handle_no_target(True)
                        self.scanner.reset()
                    else:
                        self.scanner.scan()
                self._last_tgt = None
                return
            self._last_tgt = None
            return

        self.search.update_last_target()
        if self.scanner and self.scanner.is_scanning():
            self.scanner.cancel()
            self.keys.release_all()
            time.sleep(0.2)
            if not getattr(self.keys, "dry", False):
                left, top, w, h = self.win.region
                click_bbox_center(tgt.bbox, (left, top, w, h), win=self.win)
            self._last_tgt = tgt
            return

        bw = None
        if tgt:
            x1, y1, x2, y2 = tgt.bbox
            bw = (x2 - x1) / W

        if tgt and bw is not None and bw >= self.desired_w * 0.9:
            self.keys.release_all()
            left, top, w, h = self.win.region
            if hasattr(self.keys, "dry") and self.keys.dry:
                return
            logger.debug("Atakuję cel")
            click_bbox_center(tgt.bbox, (left, top, w, h), win=self.win)
        else:
            if self.use_navigation:
                cx = int((tgt.bbox[0] + tgt.bbox[2]) / 2)
                cy = int((tgt.bbox[1] + tgt.bbox[3]) / 2)
                try:
                    minimap.navigate_to((cx, cy))
                except Exception:  # pragma: no cover - best effort
                    logger.opt(exception=True).warning("navigate_to failed")
            else:
                self.movement.move(tgt, steer, (W, H))
        self._last_tgt = tgt

    # ---- helpers ----
    def _recover_from_stuck(self) -> None:
        """Attempt to free the agent when no movement is detected."""

        if self._recovery_action == "teleport":
            try:  # pragma: no cover - best effort
                slot = self.cfg.teleport.slots[0].slot if self.cfg.teleport.slots else 1
                self.teleporter.teleport_slot(slot)
            except Exception:
                logger.opt(exception=True).warning("Teleport recovery failed")
            return

        # default action: brief rotation
        key = self.cfg.controls.keys.rotate or self.cfg.controls.keys.left
        if controller is not None:
            controller.move_camera_right(0.25)
        else:
            self.keys.press(key)
            time.sleep(0.25)
            self.keys.release(key)

    def stop(self) -> None:
        """Release resources held by the strategy.

        The method may be invoked multiple times.  Missing attributes or
        errors from underlying helpers are ignored so that ``stop`` can be
        safely called regardless of partial initialisation.
        """

        # Key handler used by the strategy itself
        try:
            if getattr(self, "keys", None):
                self.keys.stop()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Błąd podczas zatrzymywania klawiszy: {}", exc)

        # Teleporter has its own ``KeyHold`` instance
        try:
            tp = getattr(self, "teleporter", None)
            if tp and getattr(tp, "keys", None):
                tp.keys.stop()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Błąd podczas zatrzymywania teleportu: {}", exc)

        # Cancel any ongoing area scan
        try:
            scanner = getattr(self, "scanner", None)
            if scanner and hasattr(scanner, "cancel"):
                scanner.cancel()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Błąd podczas anulowania skanowania: {}", exc)

        # Close window capture if available
        try:
            if getattr(self, "win", None) and hasattr(self.win, "close"):
                self.win.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Błąd podczas zamykania okna: {}", exc)
