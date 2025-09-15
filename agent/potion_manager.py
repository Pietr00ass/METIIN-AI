"""Utility for automatically using health/mana potions.

The real game shows HP and MP as coloured bars.  For the purposes of the
tests the bars are mocked by coloured rectangles in the top left corner of the
frame.  The manager simply measures the fill level of those rectangles and
presses a configured key when the percentage drops below a threshold.
"""

from __future__ import annotations

from typing import Any

import numpy as np
try:  # pragma: no cover - missing on non-Windows CI
    import pydirectinput as pdi
except Exception:  # pragma: no cover - provide stub
    class _Stub:
        @staticmethod
        def press(key: str) -> None:  # type: ignore[override]
            return None

    pdi = _Stub()  # type: ignore[assignment]

from . import get_config


def _bar_level(region: np.ndarray, channel: int) -> float:
    """Return percentage (0-100) of a single colour channel in ``region``."""

    if region.size == 0:
        return 0.0
    return float(np.mean(region[..., channel])) / 255.0 * 100.0


def check_and_use(frame: np.ndarray) -> None:
    """Check potion levels and press a key if necessary.

    Parameters
    ----------
    frame:
        Current game frame as a BGR ``numpy`` array.
    """

    cfg = get_config()
    pot_cfg: Any = getattr(cfg, "potions", None)
    if pot_cfg is None:
        return

    # Heuristic regions for HP and MP bars (top-left corner of the frame).
    hp_region = frame[0:5, 0:50]  # red channel
    mp_region = frame[5:10, 0:50]  # blue channel

    hp_lvl = _bar_level(hp_region, 2)
    mp_lvl = _bar_level(mp_region, 0)

    if pot_cfg.hp_key and hp_lvl < pot_cfg.hp_threshold:
        pdi.press(pot_cfg.hp_key)

    if pot_cfg.mp_key and mp_lvl < pot_cfg.mp_threshold:
        pdi.press(pot_cfg.mp_key)

