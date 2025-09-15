import os
import sys
import types
import importlib

# Ensure repository root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_move_and_calibrate(monkeypatch):
    class PyAutoStub:
        PAUSE = 0

        def __init__(self):
            self.keydowns = []
            self.keyups = []
            self._pos = (0, 0)

        def keyDown(self, key):
            self.keydowns.append(key)

        def keyUp(self, key):
            self.keyups.append(key)

        def position(self):
            return self._pos

        def moveTo(self, *a, **k):
            pass

        def click(self, *a, **k):
            pass

        def press(self, *a, **k):
            pass

    pyautogui_stub = PyAutoStub()
    monkeypatch.setitem(sys.modules, "pyautogui", pyautogui_stub)

    # Stub recorder.window_capture to avoid heavy dependency
    recorder_pkg = types.ModuleType("recorder")
    recorder_pkg.__path__ = []
    wc_mod = types.ModuleType("recorder.window_capture")

    class WindowCapture:  # pragma: no cover - minimal stub
        pass

    wc_mod.WindowCapture = WindowCapture
    recorder_pkg.window_capture = wc_mod
    monkeypatch.setitem(sys.modules, "recorder", recorder_pkg)
    monkeypatch.setitem(sys.modules, "recorder.window_capture", wc_mod)

    gc = importlib.import_module("agent.game_controller")
    gc = importlib.reload(gc)

    class DummyKeys:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(gc, "KeyHold", DummyKeys)

    class DummyWindow:
        def focus(self):
            pass

        def is_foreground(self):
            return True

    cfg = types.SimpleNamespace(
        controls=types.SimpleNamespace(mouse_pause=0),
        teleport=types.SimpleNamespace(
            slots=[], click_duration=0.05, open_panel_delay=0, row_click_delay=0, after_load_delay=0
        ),
        dry_run=False,
    )
    ctrl = gc.GameController(DummyWindow(), cfg)
    monkeypatch.setattr(gc.time, "sleep", lambda t: None)
    ctrl.move_camera_right(0.5)
    ctrl.move_camera_left(0.2)
    assert pyautogui_stub.keydowns[:2] == ["right", "left"]
    assert ctrl._cam_yaw == 0.3
    ctrl.calibrate_camera()
    assert pyautogui_stub.keydowns[-1] == "left"
    assert ctrl._cam_yaw == 0.0
