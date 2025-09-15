import importlib
import os
import sys
import types

import pytest

# Ensure repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub optional heavy dependencies used by agent modules
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

cv2_stub = types.ModuleType("cv2")
cv2_stub.setNumThreads = lambda n: None
sys.modules.setdefault("cv2", cv2_stub)

ultra_stub = types.ModuleType("ultralytics")


class _DummyYOLO:
    def __init__(self, *a, **k):
        pass

    def predict(self, *a, **k):
        return []


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

sys.modules.setdefault("spacy", types.SimpleNamespace(load=lambda name: None))
sys.modules.setdefault(
    "pytesseract", types.SimpleNamespace(image_to_string=lambda img, lang="pol": "")
)

sys.modules.setdefault("mss", types.ModuleType("mss"))
sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

import numpy as np

import agent.dungeon_polana as dp
from agent.detector import Detection


class _DummyWin:
    region = (0, 0, 100, 100)

    def grab(self):
        return np.zeros((100, 100, 3), dtype=np.uint8)

    def is_foreground(self):
        return True


class _DummyTeleporter:
    def __init__(self, *a, **k):
        self.calls = []

    def teleport_slot(self, slot, page_label=None):
        self.calls.append(slot)


class _DummyDetector:
    def __init__(self, *a, **k):
        pass

    def infer(self, frame):
        return []


class _BossDetector(_DummyDetector):
    def infer(self, frame):
        return [Detection(name="boss", bbox=(0, 0, 10, 10), conf=0.9)]


class _DummyKeys:
    def __init__(self, dry=False, active_fn=None):
        self.released = []

    def release_all(self):
        self.released.append("all")

    def stop(self):
        pass


def _base_cfg():
    return {
        "paths": {"model": "", "templates_dir": ""},
        "detector": {"classes": [], "conf_thr": 0.5, "iou_thr": 0.5},
        "dungeon_polana": {"teleport_slot": 3, "boss_timeout": 1, "error_timeout": 1},
        "dry_run": True,
    }


def test_teleport_called_when_no_boss(monkeypatch):
    monkeypatch.setattr(dp, "ObjectDetector", _DummyDetector)
    tp = _DummyTeleporter()
    monkeypatch.setattr(dp, "Teleporter", lambda *a, **k: tp)
    monkeypatch.setattr(dp, "KeyHold", _DummyKeys)
    monkeypatch.setattr(dp, "parse_message", lambda frame: ("", None))
    monkeypatch.setattr(dp.time, "monotonic", lambda: 100.0)

    agent = dp.DungeonPolana(_base_cfg(), _DummyWin())
    agent.last_boss_time = 0.0
    agent.step()
    assert tp.calls == [3]


def test_error_message_triggers_teleport(monkeypatch):
    monkeypatch.setattr(dp, "ObjectDetector", _BossDetector)
    tp = _DummyTeleporter()
    monkeypatch.setattr(dp, "Teleporter", lambda *a, **k: tp)
    keys = _DummyKeys()
    monkeypatch.setattr(dp, "KeyHold", lambda *a, **k: keys)
    monkeypatch.setattr(dp, "parse_message", lambda frame: ("", "inventory full"))
    monkeypatch.setattr(dp.time, "monotonic", lambda: 100.0)

    agent = dp.DungeonPolana(_base_cfg(), _DummyWin())
    agent.step()
    assert tp.calls == [3]
    assert keys.released == ["all"]
    assert agent.last_event == "inventory full"
