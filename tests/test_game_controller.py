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


class DummyWindow:
    def __init__(self, foreground=True):
        self.focus_calls = 0
        self.foreground = foreground

    def focus(self):
        self.focus_calls += 1
        self.foreground = True

    def is_foreground(self):
        return self.foreground


def make_controller(foreground=True):
    win = DummyWindow(foreground)
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
    assert pyautogui_stub.presses == ["enter"]


def test_teleport_method_delegates():
    ctrl = make_controller()
    ctrl.teleport(5)
    assert ctrl.teleporter.calls == [5]


def test_login_focuses_and_presses_enter():
    ctrl = make_controller(foreground=False)
    ctrl.login()
    assert ctrl.win.focus_calls >= 1
    assert pyautogui_stub.presses[-1] == "enter"


def test_reset_camera_moves_to_last_position():
    ctrl = make_controller()
    # remember initial position
    pyautogui_stub._pos = (100, 200)
    ctrl.remember_camera()
    # move elsewhere and reset
    pyautogui_stub._pos = (300, 400)
    ctrl.reset_camera()
    assert pyautogui_stub.moves[-1][:2] == (100, 200)
