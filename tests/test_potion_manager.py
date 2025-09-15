import os
import sys
import types

import numpy as np

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agent.potion_manager as pm


def make_frame(hp_ratio: float, mp_ratio: float) -> np.ndarray:
    """Create dummy frame with red/blue bars representing HP/MP."""

    frame = np.zeros((20, 50, 3), dtype=np.uint8)
    hp_w = int(50 * hp_ratio)
    mp_w = int(50 * mp_ratio)
    frame[0:5, 0:hp_w, 2] = 255  # red bar
    frame[5:10, 0:mp_w, 0] = 255  # blue bar
    return frame


def test_hp_potion_trigger(monkeypatch):
    cfg = types.SimpleNamespace(
        potions=types.SimpleNamespace(
            hp_key="h", hp_threshold=50, mp_key="m", mp_threshold=50
        )
    )
    monkeypatch.setattr(pm, "get_config", lambda: cfg)
    pressed: list[str] = []
    monkeypatch.setattr(pm.pdi, "press", lambda k: pressed.append(k))

    frame = make_frame(0.3, 0.8)  # HP low
    pm.check_and_use(frame)
    assert pressed == ["h"]


def test_mp_potion_trigger(monkeypatch):
    cfg = types.SimpleNamespace(
        potions=types.SimpleNamespace(
            hp_key="h", hp_threshold=50, mp_key="m", mp_threshold=50
        )
    )
    monkeypatch.setattr(pm, "get_config", lambda: cfg)
    pressed: list[str] = []
    monkeypatch.setattr(pm.pdi, "press", lambda k: pressed.append(k))

    frame = make_frame(0.8, 0.3)  # MP low
    pm.check_and_use(frame)
    assert pressed == ["m"]


def test_no_potion_needed(monkeypatch):
    cfg = types.SimpleNamespace(
        potions=types.SimpleNamespace(
            hp_key="h", hp_threshold=50, mp_key="m", mp_threshold=50
        )
    )
    monkeypatch.setattr(pm, "get_config", lambda: cfg)
    pressed: list[str] = []
    monkeypatch.setattr(pm.pdi, "press", lambda k: pressed.append(k))

    frame = make_frame(0.9, 0.9)
    pm.check_and_use(frame)
    assert pressed == []

