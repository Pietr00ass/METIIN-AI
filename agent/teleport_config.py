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
    yaml = types.SimpleNamespace(safe_load=lambda f: {}, safe_dump=lambda data, f, **k: None)


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


def save_teleport_config(data: Dict[str, Any], path: str | Path = "config/teleport.yaml") -> None:
    """Save teleport configuration to ``path`` in YAML format."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)


_cfg = load_teleport_config()

# Delays configurable via ``config/teleport.yaml`` with sane defaults
DELAY_AFTER_PANEL: float = float(_cfg.get("delay_after_panel", 0.5))
DELAY_AFTER_TELEPORT: float = float(_cfg.get("delay_after_teleport", 1.0))
DELAY_AFTER_CHANNEL: float = float(_cfg.get("delay_after_channel", 5.0))

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
    delay: float = DELAY_AFTER_TELEPORT,
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
    time.sleep(DELAY_AFTER_PANEL)
    for x, y in positions:
        pyautogui.click(x, y)
        pyautogui.press("e")
        time.sleep(delay)
        if close_panel:
            close_panel()


def change_channel(target_ch: int, *, delay: float = DELAY_AFTER_CHANNEL) -> None:
    """Click the button for ``target_ch`` and wait for a channel switch."""

    coords = channel_buttons.get(target_ch)
    if not coords:
        return
    x, y = coords
    pyautogui.click(x, y)
    time.sleep(delay)


def main() -> None:  # pragma: no cover - helper script
    for ch in range(1, 9):
        run_positions(ch)
        if ch < 8:
            change_channel(ch + 1)


__all__ = [
    "positions_by_channel",
    "channel_buttons",
    "DELAY_AFTER_PANEL",
    "DELAY_AFTER_TELEPORT",
    "DELAY_AFTER_CHANNEL",
    "load_teleport_config",
    "save_teleport_config",
    "open_panel",
    "run_positions",
    "change_channel",
    "main",
]
