from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .detector import ObjectDetector
from .template_matcher import TemplateMatcher
from .interaction import click_bbox_center
from .game_state import GameState
from utils.classes import LOOT_CLASSES
from utils.logging_config import logger


@dataclass
class LootItem:
    """Representation of a dropped item to collect."""

    bbox: tuple[int, int, int, int]
    score: float


class LootCollector:
    """Detect dropped items using YOLO or template matching and click them."""

    def __init__(
        self,
        detector: ObjectDetector | None = None,
        matcher: TemplateMatcher | None = None,
        *,
        item_classes: Sequence[str] | None = None,
        template_name: str = "loot",
        win=None,
        state: GameState | None = None,
    ) -> None:
        self.detector = detector
        self.matcher = matcher
        self.item_classes = list(item_classes) if item_classes else list(LOOT_CLASSES)
        self.template_name = template_name
        self.win = win
        self.state = state

    # ------------------------------------------------------------------
    def _detect_yolo(self, frame: np.ndarray) -> list[LootItem]:
        if not self.detector:
            return []
        items: list[LootItem] = []
        dets = self.detector.infer(frame)
        for d in dets:
            if d.name in self.item_classes:
                x1, y1, x2, y2 = map(int, d.bbox)
                items.append(LootItem((x1, y1, x2, y2), d.conf))
        return items

    def _detect_template(self, frame: np.ndarray) -> list[LootItem]:
        if not self.matcher:
            return []
        matches = self.matcher.find_all(frame, self.template_name)
        items: list[LootItem] = []
        for m in matches:
            x, y, w, h = m.rect
            items.append(LootItem((x, y, x + w, y + h), m.score))
        return items

    def detect(self, frame: np.ndarray) -> list[LootItem]:
        """Return combined list of detected loot items."""

        items = self._detect_yolo(frame)
        items.extend(self._detect_template(frame))
        return items

    # ------------------------------------------------------------------
    def collect(self, frame: np.ndarray) -> int:
        """Click detected items and update ``GameState`` inventory counters."""

        items = self.detect(frame)
        if not items:
            return 0
        count = 0
        region = getattr(self.win, "region", (0, 0, frame.shape[1], frame.shape[0]))
        for item in items:
            if self.state and self.state.inventory_free <= 0:
                logger.debug("Inventory full; skipping remaining loot")
                break
            click_bbox_center(item.bbox, region, win=self.win)
            if self.state:
                self.state.add_items(1)
            count += 1
        return count


__all__ = ["LootCollector", "LootItem"]
