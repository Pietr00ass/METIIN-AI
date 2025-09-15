import os
import sys
import types

# Ensure repository root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub optional dependencies
pyautogui_stub = types.SimpleNamespace(moveTo=lambda *a, **k: None, click=lambda *a, **k: None, PAUSE=0)
sys.modules.setdefault("pyautogui", pyautogui_stub)

# Stub recorder.window_capture to avoid heavy dependency
recorder_pkg = types.ModuleType("recorder")
recorder_pkg.__path__ = []
wc_mod = types.ModuleType("recorder.window_capture")


class WindowCapture:  # pragma: no cover - minimal stub
    pass


wc_mod.WindowCapture = WindowCapture
recorder_pkg.window_capture = wc_mod
sys.modules.setdefault("recorder", recorder_pkg)
sys.modules.setdefault("recorder.window_capture", wc_mod)

import agent.game_controller as gc

# Replace KeyHold with a lightweight stub
class DummyKeys:
    def __init__(self, *a, **k):
        self.released = False
        self.hotkeys = []

    def release_all(self):
        self.released = True

    def hotkey(self, keys, duration=0.05):
        self.hotkeys.append((keys, duration))


gc.KeyHold = DummyKeys  # type: ignore

# Stub Teleporter to record calls
class DummyTeleporter:
    def __init__(self, win, cfg=None, controller=None):
        self.calls = []

    def teleport_slot(self, slot):
        self.calls.append(slot)
        return "ok"


gc.Teleporter = DummyTeleporter  # type: ignore


def make_controller():
    win = types.SimpleNamespace(focus=lambda: None, is_foreground=lambda: True)
    cfg = types.SimpleNamespace(
        controls=types.SimpleNamespace(mouse_pause=0),
        teleport=types.SimpleNamespace(slots=[types.SimpleNamespace(slot=2)], click_duration=0.05, open_panel_delay=0, row_click_delay=0, after_load_delay=0),
        dry_run=False,
    )
    ctrl = gc.GameController(win, cfg)
    ctrl._teleporter = DummyTeleporter(win, cfg, ctrl)
    return ctrl


def test_relog_triggers_hooks_and_teleport():
    ctrl = make_controller()
    events = []
    ctrl.add_on_disconnect(lambda: events.append("disconnect"))
    ctrl.add_on_death(lambda: events.append("death"))

    ctrl.relog()

    assert events == ["disconnect", "death"]
    assert ctrl.teleporter.calls == [2]
    assert ctrl.keys.released is True


def test_teleport_method_delegates():
    ctrl = make_controller()
    ctrl.teleport(5)
    assert ctrl.teleporter.calls == [5]
