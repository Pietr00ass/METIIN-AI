"""Teleport configuration loader and helpers."""

from __future__ import annotations

import types
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .wasd import KeyHold

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


@dataclass
class TeleportRuntimeConfig:
    """Runtime helper values derived from the YAML configuration."""

    config: Dict[str, Any]
    delay_after_panel: float
    delay_after_teleport: float
    delay_after_channel: float
    positions_by_channel: Dict[int, List[Tuple[int, int]]]
    channel_buttons: Dict[int, Tuple[int, int]]


_cfg_cache: TeleportRuntimeConfig | None = None
_cfg_mtime: float | None = None


def get_config(path: str | Path = "config/teleport.yaml") -> TeleportRuntimeConfig:
    """Return cached configuration data, reloading when the file changes."""

    global _cfg_cache, _cfg_mtime
    p = Path(path)
    try:
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        mtime = None

    if _cfg_cache is None or mtime != _cfg_mtime:
        raw = load_teleport_config(path)
        _cfg_cache = TeleportRuntimeConfig(
            config=raw,
            delay_after_panel=float(raw.get("delay_after_panel", 0.5)),
            delay_after_teleport=float(raw.get("delay_after_teleport", 1.0)),
            delay_after_channel=float(raw.get("delay_after_channel", 5.0)),
            positions_by_channel=raw.get("positions_by_channel", {}),
            channel_buttons=raw.get("channel_buttons", {}),
        )
        _cfg_mtime = mtime
    return _cfg_cache


def open_panel() -> None:  # pragma: no cover - provided by the game
    """Open the in‑game teleport panel.

    The actual implementation is expected to be supplied by the runtime
    environment.  A stub is provided so tests can monkeypatch it.
    """


def run_positions(
    channel: int,
    *,
    delay: float | None = None,
    close_panel: Callable[[], None] | None = None,
    keys: KeyHold | None = None,
) -> None:
    """Run all configured positions for ``channel``."""

    cfg = get_config()
    positions = cfg.positions_by_channel.get(channel)
    if not positions:
        return

    keys = keys or KeyHold()

    open_panel()
    time.sleep(cfg.delay_after_panel)
    sleep_delay = delay if delay is not None else cfg.delay_after_teleport
    for x, y in positions:
        pyautogui.click(x, y)
        keys.tap("e")
        time.sleep(sleep_delay)
        if close_panel:
            close_panel()


def change_channel(target_ch: int, *, delay: float | None = None) -> None:
    """Click the button for ``target_ch`` and wait for a channel switch."""

    cfg = get_config()
    coords = cfg.channel_buttons.get(target_ch)
    if not coords:
        return
    x, y = coords
    pyautogui.click(x, y)
    time.sleep(delay if delay is not None else cfg.delay_after_channel)


def main() -> None:  # pragma: no cover - helper script
    for ch in [1, 2, 3, 4]:
        run_positions(ch)
        if ch < 4:
            change_channel(ch + 1)


__all__ = [
    "load_teleport_config",
    "save_teleport_config",
    "get_config",
    "open_panel",
    "run_positions",
    "change_channel",
    "main",
]
