import os
import sys
import types
from dataclasses import dataclass
from typing import Tuple

import pytest

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

# Stub pyautogui to avoid real mouse interaction
pyautogui_stub = types.SimpleNamespace(moveTo=lambda *a, **k: None, click=lambda *a, **k: None, PAUSE=0)
sys.modules.setdefault("pyautogui", pyautogui_stub)

# Stub recorder.window_capture so ChannelSwitcher can be imported without dependencies
recorder_pkg = types.ModuleType("recorder")
recorder_pkg.__path__ = []
wc_mod = types.ModuleType("recorder.window_capture")


class WindowCapture:
    def __init__(self, *a, **k):
        self.region = (0, 0, 300, 300)

    def grab(self):
        import numpy as np

        return np.zeros((300, 300, 4), dtype=np.uint8)

    def focus(self):
        pass

    def is_foreground(self):
        return True


wc_mod.WindowCapture = WindowCapture
recorder_pkg.window_capture = wc_mod
sys.modules.setdefault("recorder", recorder_pkg)
sys.modules.setdefault("recorder.window_capture", wc_mod)

# Provide a minimal TemplateMatcher stub used during import
_tm_mod = types.ModuleType("agent.template_matcher")


class _TM:
    def __init__(self, *a, **k):
        pass

    def find(self, *a, **k):
        return None


@dataclass
class _Match:
    rect: Tuple[int, int, int, int]
    center: Tuple[int, int]
    score: float


_tm_mod.TemplateMatcher = _TM
_tm_mod.TemplateMatch = _Match
sys.modules.setdefault("agent.template_matcher", _tm_mod)

import agent.channel as channel
from config.models import AgentConfig, ChannelConfig, PathsConfig, WindowConfig


class KH:
    def __init__(self):
        self.calls: list[tuple[list[str], float]] = []

    def hotkey(self, keys, duration=0.05):
        self.calls.append((keys, duration))


def _setup_templates(tmp_path):
    for i in range(1, 9):
        (tmp_path / f"ch{i}.png").touch()


def test_switch_uses_configured_hotkeys(tmp_path):
    _setup_templates(tmp_path)
    cfg = AgentConfig(
        paths=PathsConfig(templates_dir=str(tmp_path)),
        window=WindowConfig(title_substr="dummy"),
        channel=ChannelConfig(hotkeys={1: "f7", 2: "f8"}),
    )
    keys = KH()
    cs = channel.ChannelSwitcher(
        WindowCapture(), cfg.paths.templates_dir, dry=False, keys=keys, hotkeys=cfg.channel.hotkeys
    )
    assert cs.switch(1, post_wait=0) is True
    assert cs.switch(2, post_wait=0) is True
    assert keys.calls == [(["f7"], 0.05), (["f8"], 0.05)]
