"""Configuration loader for the Metin2 agent.

This module exposes :func:`get_config` which loads ``config/agent.yaml``
and merges it with a set of sane defaults.  Other modules simply import
:func:`get_config` to obtain a dictionary with configuration values.
Missing entries fall back to defaults so that incomplete configuration files
never cause runtime errors.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import yaml

# ---------------------------------------------------------------------------
# Default configuration used when keys are missing from the YAML file.
# ---------------------------------------------------------------------------
DEFAULT_CFG: Dict[str, Any] = {
    "window": {"title_substr": "Metin2"},
    "paths": {
        "templates_dir": "assets/templates",
        "model": "runs/detect/train/weights/best.pt",
    },
    "controls": {
        "keys": {
            "forward": "w",
            "left": "a",
            "back": "s",
            "right": "d",
            "rotate": "e",
        },
        "key_repeat_ms": 60,
        "mouse_pause": 0.02,
    },
    "detector": {
        "classes": ["metin", "boss", "potwory"],
        "conf_thr": 0.5,
        "iou_thr": 0.45,
    },
    "policy": {"deadzone_x": 0.05, "desired_box_w": 0.12},
    "stuck": {"flow_window": 0.8, "min_flow_mag": 0.7, "rotate_ms_on_stuck": 250},
    "scan": {
        "period": 0.066,
        "key": "e",
        "sweeps": 8,
        "sweep_ms": 250,
        "idle_sec": 1.5,
        "pause": 0.12,
    },
    "cooldowns": {"slot_min": 10},
    "priority": ["boss", "metin", "potwory"],
    "teleport": {
        "slots": [],
        "no_target_sec": 10,
        "channel_every": 8,
    },
    "channels": [1, 2, 3, 4, 5, 6, 7, 8],
    "cycle": {
        "ch_from": 1,
        "ch_to": 8,
        "slots": [1, 2, 3, 4, 5, 6, 7, 8],
        "per_spot_sec": 90,
        "clear_sec": 6,
    },
}


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``updates`` into ``base``."""

    for key, val in updates.items():
        if isinstance(val, dict):
            base[key] = _deep_update(base.get(key, {}), val)
        else:
            base[key] = val
    return base


_cfg: Dict[str, Any] | None = None


def load_config(path: str | Path = "config/agent.yaml") -> Dict[str, Any]:
    """Load configuration file and merge with defaults."""

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    cfg = copy.deepcopy(DEFAULT_CFG)
    _deep_update(cfg, data)
    return cfg


def get_config(path: str | Path = "config/agent.yaml") -> Dict[str, Any]:
    """Return cached configuration dictionary.

    The configuration is loaded on first use and then cached for subsequent
    calls.  ``path`` is honoured only on the first invocation.
    """

    global _cfg
    if _cfg is None:
        _cfg = load_config(path)
    return _cfg


__all__ = ["get_config", "load_config"]
