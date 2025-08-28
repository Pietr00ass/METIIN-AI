import importlib
import os
import sys
import types

import pytest

# Make repository root importable and stub optional heavy dependencies.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

sys.modules.pop("numpy", None)
np = importlib.import_module("numpy")

cv2_stub = types.ModuleType("cv2")
cv2_stub.setNumThreads = lambda n: None
sys.modules["cv2"] = cv2_stub

ultra_stub = types.ModuleType("ultralytics")


class _DummyYOLO:
    def __init__(self, *args, **kwargs):
        pass

    def predict(self, *args, **kwargs):
        class _Res:
            names = {}
            boxes = []

        return [_Res()]


ultra_stub.YOLO = _DummyYOLO
sys.modules.setdefault("ultralytics", ultra_stub)

pyautogui_stub = types.ModuleType("pyautogui")
pyautogui_stub.moveTo = lambda *a, **k: None
pyautogui_stub.click = lambda *a, **k: None
pyautogui_stub.PAUSE = 0
sys.modules.setdefault("pyautogui", pyautogui_stub)

easyocr_stub = types.ModuleType("easyocr")
easyocr_stub.Reader = lambda *a, **k: None
sys.modules.setdefault("easyocr", easyocr_stub)

teleport_mod = types.ModuleType("agent.teleport")


class _DummyTeleporter:
    def __init__(self, *a, **k):
        pass

    def teleport_slot(self, *a, **k):
        pass


teleport_mod.Teleporter = _DummyTeleporter
sys.modules["agent.teleport"] = teleport_mod

channel_mod = types.ModuleType("agent.channel")


class _DummyChannelSwitcher:
    def __init__(self, *a, **k):
        pass

    def switch(self, *a, **k):
        pass


channel_mod.ChannelSwitcher = _DummyChannelSwitcher
sys.modules["agent.channel"] = channel_mod

import agent.hunt_destroy as hd


class _StubKeyHold:
    def __init__(self, dry=False, active_fn=None):
        self.down = set()
        self.pressed = []
        self.released = []

    def press(self, key):
        if key not in self.down:
            self.down.add(key)
            self.pressed.append(key)

    def release(self, key):
        if key in self.down:
            self.down.remove(key)
            self.released.append(key)

    def release_all(self):
        for k in list(self.down):
            self.release(k)

    def stop(self):
        pass


class _DummyDetector:
    def __init__(self, *a, **k):
        self.calls = 0

    def infer(self, frame):
        if self.calls == 0:
            bbox = (60, 40, 70, 60)
        else:
            bbox = (30, 40, 40, 60)
        self.calls += 1
        return [{"name": "enemy", "bbox": bbox}]


class _DummyAvoid:
    def steer(self, frame):
        return None


class _EmptyDetector:
    def __init__(self, *a, **k):
        pass

    def infer(self, frame):
        return []


class _StubSearch:
    def __init__(self, *a, **k):
        self.calls = 0

    def handle_no_target(self, spin_done):
        self.calls += 1

    def update_last_target(self):
        pass


class _DummyWin:
    region = (0, 0, 100, 100)

    def grab(self):
        return np.zeros((100, 100, 3), dtype=np.uint8)

    def is_foreground(self):
        return True


def _pick_target(dets, size, priority_order=None):
    return dets[0] if dets else None


def test_hunt_destroy_continuous_movement(monkeypatch):
    monkeypatch.setattr(hd, "ObjectDetector", _DummyDetector)
    monkeypatch.setattr(hd, "CollisionAvoid", lambda: _DummyAvoid())
    monkeypatch.setattr(hd, "KeyHold", _StubKeyHold)
    monkeypatch.setattr(hd, "pick_target", _pick_target)
    monkeypatch.setattr(hd, "click_bbox_center", lambda *a, **k: None)

    cfg = {
        "paths": {"model": "", "templates_dir": ""},
        "detector": {"classes": [], "conf_thr": 0.5, "iou_thr": 0.5},
        "policy": {"desired_box_w": 0.2, "deadzone_x": 0.1},
        "dry_run": True,
    }

    agent = hd.HuntDestroy(cfg, _DummyWin())

    agent.step()
    assert agent.keys.down == {"d", "w"}
    assert set(agent.keys.pressed) == {"d", "w"}
    assert agent.keys.released == []

    agent.step()
    assert agent.keys.down == {"a", "w"}
    assert agent.keys.pressed.count("w") == 1
    assert agent.keys.pressed.count("d") == 1
    assert agent.keys.pressed.count("a") == 1
    assert agent.keys.released == ["d"]


def test_spin_no_target(monkeypatch):
    monkeypatch.setattr(hd, "ObjectDetector", _EmptyDetector)
    monkeypatch.setattr(hd, "CollisionAvoid", lambda: _DummyAvoid())
    monkeypatch.setattr(hd, "KeyHold", _StubKeyHold)
    monkeypatch.setattr(hd, "SearchManager", _StubSearch)
    monkeypatch.setattr(hd, "pick_target", lambda *a, **k: None)
    cfg = {
        "paths": {"model": "", "templates_dir": ""},
        "detector": {"classes": [], "conf_thr": 0.5, "iou_thr": 0.5},
        "policy": {"desired_box_w": 0.2, "deadzone_x": 0.1},
        "dry_run": True,
    }
    agent = hd.HuntDestroy(cfg, _DummyWin())
    times = iter([0, 3, 4.1])
    monkeypatch.setattr(hd.time, "time", lambda: next(times))

    agent.step()
    assert agent.keys.down == {"a"}
    assert agent.search.calls == 0

    agent.step()
    assert agent.keys.down == {"a"}
    assert agent.search.calls == 0

    agent.step()
    assert agent.keys.down == set()
    assert agent.search.calls == 1
    assert agent._spin_dir == "d"
