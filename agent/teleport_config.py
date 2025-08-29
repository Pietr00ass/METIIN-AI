"""Teleport configuration loader and helpers."""

from __future__ import annotations

import types
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Callable

try:  # pyautogui is optional during tests
    import pyautogui
except Exception:  # pragma: no cover - provide a tiny stub
    pyautogui = types.SimpleNamespace(click=lambda *a, **k: None, press=lambda *a, **k: None)

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

def open_panel() -> None:  # pragma: no cover - provided by the game
    """Open the in‑game teleport panel.

    The actual implementation is expected to be supplied by the runtime
    environment.  A stub is provided so tests can monkeypatch it.
    """


def run_positions(
    channel: int,
    *,
    delay: float = 1.0,
    close_panel: Callable[[], None] | None = None,
) -> None:
    """Run all configured positions for ``channel``.

    The teleport panel is opened once via :func:`open_panel`.  For each of the
    eight stored positions the function performs a click, sends the interaction
    key ``E`` and waits ``delay`` seconds for in‑game actions to complete.  When
    ``close_panel`` is provided it is invoked after each position which allows
    the caller to close the panel between teleports if necessary.
    """

    positions = positions_by_channel.get(channel)
    if not positions:
        return

    open_panel()
    for x, y in positions:
        pyautogui.click(x, y)
        pyautogui.press("e")
        time.sleep(delay)
        if close_panel:
            close_panel()


__all__ = [
    "positions_by_channel",
    "channel_buttons",
    "load_teleport_config",
    "open_panel",
    "run_positions",
]
