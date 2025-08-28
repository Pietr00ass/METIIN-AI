import importlib
import os
import sys
import types

import pytest

sys.modules.pop("numpy", None)
np = importlib.import_module("numpy")

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

# Stub pyautogui to avoid real mouse interaction
pyautogui_stub = types.SimpleNamespace(
    moveTo=lambda *a, **k: None, click=lambda *a, **k: None
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


tm_stub.TemplateMatcher = _TM
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


def _setup_templates(tmp_path):
    for i in range(1, 9):
        (tmp_path / f"ch{i}.png").touch()


def test_switch_clicks_on_success(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return {"center": (50, 60)}

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    moves, clicks = [], []
    monkeypatch.setattr(channel.pyautogui, "moveTo", lambda *a, **k: moves.append(1))
    monkeypatch.setattr(channel.pyautogui, "click", lambda *a, **k: clicks.append(1))
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=False)
    assert cs.switch(1, tries=1, post_wait=0) is True
    assert moves and clicks


def test_switch_returns_false_when_not_found(tmp_path, monkeypatch):
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
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=False)
    assert cs.switch(1, tries=1, post_wait=0) is False


def test_switch_uses_keys_when_not_found(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return None

    monkeypatch.setattr(channel, "TemplateMatcher", TM)

    presses = []
    focuses = []

    class KH:
        def press(self, key):
            presses.append(f"down-{key}")

        def release(self, key):
            presses.append(f"up-{key}")

    class Win(DummyWin):
        def focus(self):
            focuses.append(1)

    cs = channel.ChannelSwitcher(Win(), str(tmp_path), dry=False, keys=KH())
    assert cs.switch(3, tries=1, post_wait=0) is True
    assert presses == ["down-ctrl", "down-3", "up-3", "up-ctrl"]
    assert focuses, "focus should be called before sending keys"


def test_next_wraps(tmp_path):
    _setup_templates(tmp_path)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True)
    assert cs.next(1) == 2
    assert cs.next(8) == 1


def test_cycle_until_target_seen(tmp_path, monkeypatch):
    _setup_templates(tmp_path)

    # Patch out template matcher to avoid real image lookup
    class TM:
        def __init__(self, *a, **k):
            pass

        def find(self, frame, name, **kw):
            return {"center": (50, 60)}

    monkeypatch.setattr(channel, "TemplateMatcher", TM)
    cs = channel.ChannelSwitcher(DummyWin(), str(tmp_path), dry=True)

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
        cs.cycle_until_target_seen(
            check_fn, settle=0, timeout_per_ch=0, max_rounds=1
        )
        is True
    )
    assert switched == [2, 3]
