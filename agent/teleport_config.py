"""Teleport configuration loader and helpers."""

from __future__ import annotations

import types
import time
from dataclasses import dataclass, field
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
    positions: List[Tuple[int, int]]
    channel_buttons: Dict[int, Tuple[int, int]]
    positions_by_channel: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)


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
            positions=[tuple(p) for p in raw.get("positions", [])],
            channel_buttons={
                int(k): tuple(v) for k, v in raw.get("channel_buttons", {}).items()
            },
            positions_by_channel={
                int(k): [tuple(p) for p in v]
                for k, v in raw.get("positions_by_channel", {}).items()
            },
        )
        _cfg_mtime = mtime
    return _cfg_cache


def open_panel(keys: KeyHold | None = None) -> None:
    """Open the in‑game teleport panel using ``Ctrl+X``."""

    keys = keys or KeyHold()
    keys.hotkey(["ctrl", "x"], duration=0.05)

def run_positions(
    channel: int,
    *,
    delay: float | None = None,
    close_panel: Callable[[], None] | None = None,
    keys: KeyHold | None = None,
) -> None:
    """Run all configured positions."""

    cfg = get_config()
    positions = cfg.positions_by_channel.get(channel, cfg.positions)
    if not positions:
        return

    keys = keys or KeyHold()

    open_panel()
    time.sleep(cfg.delay_after_panel)
    sleep_delay = delay if delay is not None else cfg.delay_after_teleport
    for x, y in positions:
        pyautogui.moveTo(x, y)
        pyautogui.click(button="left")
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
    pyautogui.moveTo(x, y)
    pyautogui.click(button="left")
    time.sleep(delay if delay is not None else cfg.delay_after_channel)


def cycle_channels(channels: list[int]) -> None:
    """Run positions for each channel and switch between them."""

    for idx, ch in enumerate(channels):
        run_positions(ch)
        if idx + 1 < len(channels):
            change_channel(channels[idx + 1])


def main() -> None:  # pragma: no cover - helper script
    cycle_channels([1, 2, 3, 4])


__all__ = [
    "load_teleport_config",
    "save_teleport_config",
    "get_config",
    "open_panel",
    "run_positions",
    "change_channel",
    "main",
]
