"""Teleport configuration loader."""

from __future__ import annotations

import types
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except Exception:  # pragma: no cover - yaml is optional
    yaml = types.SimpleNamespace(safe_load=lambda f: {})


def load_teleport_config(path: str | Path = "config/teleport.yaml") -> Dict[str, Any]:
    """Load teleport configuration from ``path``.

    Missing files result in an empty configuration.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    return data


_cfg = load_teleport_config()

# Public mappings with fallback to empty structures
positions_by_channel: Dict[int, List[Tuple[int, int]]] = _cfg.get(
    "positions_by_channel", {}
)
channel_buttons: Dict[int, Tuple[int, int]] = _cfg.get("channel_buttons", {})

__all__ = ["positions_by_channel", "channel_buttons", "load_teleport_config"]
