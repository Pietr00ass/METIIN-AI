from __future__ import annotations

"""Coordinate based teleporter."""

import logging
import time
from enum import Enum

import pyautogui

from recorder.window_capture import WindowCapture

from . import AgentConfig, get_config, teleport_config as tc

try:  # pragma: no cover - prefer pydirectinput if available
    from pydirectinput import KeyHold  # type: ignore
except Exception:  # pragma: no cover - fallback to local implementation
    from .wasd import KeyHold

CFG = get_config()

logger = logging.getLogger(__name__)


class TeleportResult(Enum):
    """Possible outcomes of a teleport attempt."""

    OK = "ok"
    TEMPLATE_NOT_FOUND = "template_not_found"
    OCR_MISS = "ocr_miss"
    WINDOW_NOT_FOREGROUND = "window_not_foreground"


class Teleporter:
    """Simple teleporter that clicks preconfigured coordinates.

    All template and OCR based detection has been removed.  Teleportation now
    relies solely on sending the ``Ctrl+X`` hotkey to open the teleport panel
    and clicking coordinates loaded from ``config/teleport.yaml``.
    """

    def __init__(
        self,
        win: WindowCapture,
        templates_dir: str | None = None,
        use_ocr: bool = False,
        dry: bool = False,
        cfg: AgentConfig | dict | None = None,
    ) -> None:
        if cfg is None:
            cfg = CFG
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        pyautogui.PAUSE = self.cfg.controls.mouse_pause
        self.win = win
        self.dry = dry
        self.keys = KeyHold(dry=self.dry, active_fn=getattr(self.win, "is_foreground", None))

        tp_cfg = self.cfg.teleport
        self.click_duration = tp_cfg.click_duration
        self.open_panel_delay = tp_cfg.open_panel_delay
        self.row_click_delay = tp_cfg.row_click_delay
        self.after_load_delay = tp_cfg.after_load_delay

    def _safe_click(self, x: int, y: int) -> None:
        if self.dry:
            return
        self.win.focus()
        if not self.win.is_foreground():
            return
        pyautogui.moveTo(x, y, duration=self.click_duration)
        pyautogui.click()

    def open_panel(self, max_attempts: int = 3) -> bool:
        """Open teleport panel using ``Ctrl+X`` without any verification."""

        self.win.focus()
        if not self.win.is_foreground():
            logger.debug("Window is not in foreground before opening teleport panel")
            return False

        for attempt in range(max_attempts):
            logger.debug("Attempt %d to open teleport panel", attempt + 1)
            if not self.dry:
                self.keys.hotkey(["ctrl", "x"], duration=0.05)
            time.sleep(self.open_panel_delay)
            if not self.win.is_foreground():
                logger.debug(
                    "Window lost foreground after keypress on attempt %d", attempt + 1
                )
                return False
            return True
        return True

    def close_panel(self) -> None:
        """Close the teleport panel if it is open."""

        if self.dry:
            return
        self.keys.tap("esc")

    # ---- teleportation ----
    def teleport_slot(self, slot: int, page_label: str | None = None) -> TeleportResult:
        """Teleport to the configured ``slot``.

        ``page_label`` is accepted for backwards compatibility but ignored.
        Coordinates are loaded from ``config/teleport.yaml``.
        """

        logger.debug("Teleporting to slot %s via coordinates", slot)
        if not self.open_panel():
            return TeleportResult.WINDOW_NOT_FOREGROUND

        cfg = tc.get_config()
        positions = cfg.positions
        if slot < 1 or slot > len(positions):
            logger.info("Slot %s not configured", slot)
            return TeleportResult.TEMPLATE_NOT_FOUND

        x, y = positions[slot - 1]
        logger.debug("Clicking teleport slot at (%d, %d)", x, y)
        self._safe_click(x, y)
        time.sleep(self.row_click_delay)
        if not self.dry:
            self.keys.tap("e")
        time.sleep(self.after_load_delay)
        logger.info("Teleportation to slot %s successful", slot)
        return TeleportResult.OK

    def teleport(self, slot: int, page_label: str | None = None) -> TeleportResult:
        """Compatibility wrapper named ``teleport``."""
        return self.teleport_slot(slot, page_label)


__all__ = ["Teleporter", "TeleportResult"]
