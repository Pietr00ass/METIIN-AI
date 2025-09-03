import importlib
import os
import sys
import types
from dataclasses import dataclass
from typing import Tuple

import pytest

sys.modules.pop("numpy", None)
np = importlib.import_module("numpy")

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

# Stub pyautogui to avoid real mouse interaction
pyautogui_stub = types.SimpleNamespace(
    moveTo=lambda *a, **k: None, click=lambda *a, **k: None, PAUSE=0
)
sys.modules.setdefault("pyautogui", pyautogui_stub)

# Stub recorder.window_capture so ChannelSwitcher can be imported without dependencies
recorder_pkg = types.ModuleType("recorder")
recorder_pkg.__path__ = []
wc_mod = types.ModuleType("recorder.window_capture")


class WindowCapture:
    def __init__(self, *a, **k):
        self.region = (0, 0, 300, 300)

    def grab(self):
        return np.zeros((300, 300, 4), dtype=np.uint8)

    def focus(self):
        pass


recorder_pkg.window_capture = wc_mod
wc_mod.WindowCapture = WindowCapture
sys.modules.setdefault("recorder", recorder_pkg)
sys.modules.setdefault("recorder.window_capture", wc_mod)

# Provide a minimal TemplateMatcher stub used during import; tests will patch as needed
tm_stub = types.ModuleType("agent.template_matcher")


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


tm_stub.TemplateMatcher = _TM
tm_stub.TemplateMatch = _Match
sys.modules.setdefault("agent.template_matcher", tm_stub)

import agent.channel as channel


class DummyWin:
    def __init__(self):
        self.region = (0, 0, 300, 300)

    def grab(self):
        return np.zeros((300, 300, 4), dtype=np.uint8)

    def focus(self):
        pass

    def is_foreground(self):
        return True


class KH:
    def hotkey(self, keys, duration=0.05):
        pass


def _setup_templates(tmp_path):
    for i in range(1, 9):
        (tmp_path / f"ch{i}.png").touch()


def test_find_button_returns_template_match(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return channel.TemplateMatch(rect=(0, 0, 10, 10), center=(5, 5), score=0.95)

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True, keys=KH())
    frame = np.zeros((300, 300, 3), dtype=np.uint8)
    match = cs.find_button(frame, 1)
    assert isinstance(match, channel.TemplateMatch)
    assert match.center == (5, 5)


def test_switch_clicks_on_success(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return channel.TemplateMatch(
                rect=(0, 0, 10, 10), center=(50, 60), score=0.9
            )

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    moves, clicks = [], []
    monkeypatch.setattr(channel.pyautogui, "moveTo", lambda *a, **k: moves.append(1))
    monkeypatch.setattr(channel.pyautogui, "click", lambda *a, **k: clicks.append(1))
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=False, keys=KH())
    assert cs.switch(1, tries=1, post_wait=0) is True
    assert moves and clicks


def test_switch_uses_keys_without_mouse_when_not_found(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return None

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    moves, clicks = [], []
    monkeypatch.setattr(channel.pyautogui, "moveTo", lambda *a, **k: moves.append(1))
    monkeypatch.setattr(channel.pyautogui, "click", lambda *a, **k: clicks.append(1))
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=False, keys=KH())
    assert cs.switch(1, tries=1, post_wait=0) is True
    assert not moves and not clicks, "mouse should not be used when keys are available"


def test_error_when_no_keyhold(tmp_path):
    _setup_templates(tmp_path)
    # With ``dry=False`` and without providing ``keys`` the switcher should
    # refuse to initialise because ``pydirectinput`` is missing in tests.
    with pytest.raises(RuntimeError):
        channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=False)


def test_switch_uses_keys_when_not_found(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return None

    monkeypatch.setattr(channel, "TemplateMatcher", TM)

    hotkey_calls: list[tuple[list[str], float]] = []
    focuses = []

    class KH:
        def hotkey(self, keys, duration=0.05):
            hotkey_calls.append((keys, duration))

    class Win(DummyWin):
        def focus(self):
            focuses.append(1)

    cs = channel.ChannelSwitcher(Win(), str(tmp_path), dry=False, keys=KH())
    assert cs.switch(3, tries=1, post_wait=0) is True
    assert hotkey_calls == [(["numpad3"], 0.05)]
    assert focuses, "focus should be called before sending keys"


def test_custom_hotkeys_respected(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return None

    monkeypatch.setattr(channel, "TemplateMatcher", TM)

    hotkey_calls: list[tuple[list[str], float]] = []

    class KH:
        def hotkey(self, keys, duration=0.05):
            hotkey_calls.append((keys, duration))

    custom = {i: str(i) for i in range(1, 9)}
    cs = channel.ChannelSwitcher(
        DummyWin(), str(tmp_path), dry=False, keys=KH(), hotkeys=custom
    )
    assert cs.switch(2, tries=1, post_wait=0) is True
    assert hotkey_calls == [(["2"], 0.05)]


def test_next_wraps(tmp_path):
    _setup_templates(tmp_path)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True, keys=KH())
    assert cs.next(1) == 2
    assert cs.next(8) == 1


def test_cycle_until_target_seen(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    # Patch out template matcher to avoid real image lookup
    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return channel.TemplateMatch(
                rect=(0, 0, 10, 10), center=(50, 60), score=0.9
            )

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True, keys=KH())

    # Start from channel 1
    monkeypatch.setattr(cs, "current_channel_guess", lambda thresh=0.82: 1)

    switched = []

    def fake_switch(ch, **kw):
        switched.append(ch)
        return True

    monkeypatch.setattr(cs, "switch", fake_switch)

    calls = {"n": 0}

    def check_fn():
        calls["n"] += 1
        return calls["n"] >= 3

    assert (
        cs.cycle_until_target_seen(check_fn, settle=0, timeout_per_ch=0, max_rounds=1)
        is True
    )
    assert switched == [2, 3]


def test_default_hotkeys_mapping(tmp_path):
    _setup_templates(tmp_path)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True, keys=KH())
    assert cs.hotkeys == {i: f"numpad{i}" for i in range(1, 9)}
