from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from utils.logging_config import logger
from utils.requirements_check import ensure_tesseract_available

try:  # pragma: no cover - import guard for optional OCR dependency
    import pytesseract as _pytesseract
except ImportError as exc:  # pragma: no cover - handled by ensure_ocr_ready
    _PYTESSERACT_IMPORT_ERROR = exc
    pytesseract = None  # type: ignore[assignment]
else:
    _PYTESSERACT_IMPORT_ERROR = None
    pytesseract = _pytesseract


@dataclass
class HudRoi:
    x: int
    y: int
    w: int
    h: int

    @classmethod
    def from_list(cls, roi: Iterable[int]) -> "HudRoi | None":
        vals = list(roi)
        if len(vals) != 4:
            return None
        x, y, w, h = vals
        if w <= 0 or h <= 0:
            return None
        return cls(x, y, w, h)

    def crop(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        x1 = max(0, min(width, self.x))
        y1 = max(0, min(height, self.y))
        x2 = max(0, min(width, self.x + self.w))
        y2 = max(0, min(height, self.y + self.h))
        if x2 <= x1 or y2 <= y1:
            return np.zeros((0, 0, 3), dtype=frame.dtype)
        return frame[y1:y2, x1:x2]


class HudOcr:
    """Extract HUD text for HP/MP ratios and inventory status."""

    def __init__(self, cfg) -> None:
        self.update_config(cfg)

    def update_config(self, cfg) -> None:
        self.hp_roi = HudRoi.from_list(getattr(cfg, "hp_roi", []))
        self.mp_roi = HudRoi.from_list(getattr(cfg, "mp_roi", []))
        self.inventory_roi = HudRoi.from_list(getattr(cfg, "inventory_roi", []))
        self.arrows_roi = HudRoi.from_list(getattr(cfg, "arrows_roi", []))

    def update_state(self, frame: np.ndarray, state) -> None:
        if state is None:
            return
        state.hp_ratio = self._parse_ratio(self._ocr_roi(frame, self.hp_roi))
        state.mp_ratio = self._parse_ratio(self._ocr_roi(frame, self.mp_roi))
        inv_text = self._ocr_roi(frame, self.inventory_roi)
        inv_state = self._parse_inventory(inv_text)
        if inv_state is not None:
            state.inventory_occupied, state.inventory_slots, state.inventory_full = inv_state
        arrows_text = self._ocr_roi(frame, self.arrows_roi)
        if arrows_text:
            state.arrows_empty = self._contains_any(
                arrows_text.lower(), "brak", "strzal", "strzał", "arrow"
            )

    def _ocr_roi(self, frame: np.ndarray, roi: HudRoi | None) -> str:
        if roi is None:
            return ""
        if pytesseract is None:
            return ""
        try:
            ensure_tesseract_available(pytesseract)
        except Exception:  # pragma: no cover - best effort
            return ""
        crop = roi.crop(frame)
        if crop.size == 0:
            return ""
        config = "--psm 7 -c tessedit_char_whitelist=0123456789/%abcdefghijklmnopqrstuvwxyz"
        try:
            return pytesseract.image_to_string(crop, config=config).strip()
        except Exception:  # pragma: no cover - defensive
            logger.opt(exception=True).warning("HUD OCR failed")
            return ""

    @staticmethod
    def _parse_ratio(text: str) -> float | None:
        if not text:
            return None
        cleaned = text.replace(" ", "")
        match = re.search(r"(\d+)\s*/\s*(\d+)", cleaned)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return current / total * 100.0
            return None
        match = re.search(r"(\d+)\s*%", cleaned)
        if match:
            return float(match.group(1))
        digits = re.findall(r"\d+", cleaned)
        if len(digits) == 1:
            return float(digits[0])
        return None

    @staticmethod
    def _parse_inventory(text: str) -> tuple[int, int, bool] | None:
        if not text:
            return None
        match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if not match:
            return None
        occupied = int(match.group(1))
        total = int(match.group(2))
        return occupied, total, total > 0 and occupied >= total

    @staticmethod
    def _contains_any(text: str, *subs: str) -> bool:
        return any(sub in text for sub in subs)


__all__ = ["HudOcr", "HudRoi"]
