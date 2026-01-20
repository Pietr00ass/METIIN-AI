from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

from .detector import Detection
from config.models import DungeonFsmConfig, DungeonStateConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    reason: str


class DungeonFSM:
    """Finite state machine for multi-floor dungeon navigation."""

    def __init__(self, cfg: DungeonFsmConfig):
        self.cfg = cfg
        self.state = cfg.initial_state
        now = time.monotonic()
        self._entered_at = now
        self._last_transition = now

    def reset(self, state: str | None = None) -> None:
        self.state = state or self.cfg.initial_state
        now = time.monotonic()
        self._entered_at = now
        self._last_transition = now

    def update(self, ocr_event: str | None, detections: Iterable[Detection]) -> Transition | None:
        state_cfg = self.cfg.states.get(self.state)
        if state_cfg is None:
            logger.warning("Unknown dungeon FSM state: %s", self.state)
            return None
        detected_names = {det.name for det in detections}
        if not self._requirements_met(state_cfg, detected_names, ocr_event):
            return None
        now = time.monotonic()
        if now - self._last_transition < state_cfg.cooldown_sec:
            return None
        reason = self._trigger_reason(state_cfg, detected_names, ocr_event, now)
        if reason is None or state_cfg.next_state is None:
            return None
        transition = Transition(self.state, state_cfg.next_state, reason)
        self.state = state_cfg.next_state
        self._entered_at = now
        self._last_transition = now
        return transition

    def _requirements_met(
        self,
        state_cfg: DungeonStateConfig,
        detected_names: set[str],
        ocr_event: str | None,
    ) -> bool:
        if state_cfg.require_detections and not set(state_cfg.require_detections).issubset(detected_names):
            return False
        if state_cfg.require_ocr_events and (ocr_event not in set(state_cfg.require_ocr_events)):
            return False
        return True

    def _trigger_reason(
        self,
        state_cfg: DungeonStateConfig,
        detected_names: set[str],
        ocr_event: str | None,
        now: float,
    ) -> str | None:
        if ocr_event and ocr_event in set(state_cfg.ocr_triggers):
            return f"ocr:{ocr_event}"
        if state_cfg.detect_triggers and set(state_cfg.detect_triggers).intersection(detected_names):
            return "detection"
        if state_cfg.timeout_sec and (now - self._entered_at) >= state_cfg.timeout_sec:
            return "timeout"
        return None


__all__ = ["DungeonFSM", "Transition"]
