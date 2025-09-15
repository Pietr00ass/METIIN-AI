import os
import sys
import types

# Ensure repository root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub optional dependencies
class PyAutoStub:
    PAUSE = 0

    def __init__(self):
        self.moves = []
        self.presses = []
        self._pos = (0, 0)

    def moveTo(self, x, y, duration=0):
        self.moves.append((x, y, duration))
        self._pos = (x, y)

    def click(self, *a, **k):
        pass

    def press(self, key):
        self.presses.append(key)

    def position(self):
        return self._pos


pyautogui_stub = PyAutoStub()
sys.modules.setdefault("pyautogui", pyautogui_stub)

# Stub recorder.window_capture
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
from agent.game_state import GameState


class DummyWindow:
    def __init__(self):
        self.focus_calls = 0
        self.foreground = True

    def focus(self):
        self.focus_calls += 1

    def is_foreground(self):
        return self.foreground


def make_controller():
    cfg = types.SimpleNamespace(
        controls=types.SimpleNamespace(mouse_pause=0),
        teleport=types.SimpleNamespace(slots=[], click_duration=0.05, open_panel_delay=0, row_click_delay=0, after_load_delay=0),
        dry_run=True,
    )
    win = DummyWindow()

    class DummyKeys:
        def __init__(self, *a, **k):
            pass

        def release_all(self):
            pass

    class DummyTeleporter:
        def __init__(self, *a, **k):
            pass

        def teleport_slot(self, slot):
            return "ok"

    gc.KeyHold = DummyKeys  # type: ignore
    gc.Teleporter = DummyTeleporter  # type: ignore
    return gc.GameController(win, cfg)


def test_game_state_defaults_and_reset():
    state = GameState()
    assert state.mounted is False
    assert state.equipment_open is False
    assert state.minimap_open is False
    state.mounted = state.equipment_open = state.minimap_open = True
    state.reset()
    assert state == GameState()


def test_controller_reset_state():
    ctrl = make_controller()
    ctrl.state.mounted = True
    ctrl.state.equipment_open = True
    ctrl.state.minimap_open = True
    ctrl.reset_state()
    assert ctrl.state == GameState()
