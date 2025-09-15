import os
import sys
import types

import numpy as np

# Ensure repository root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub pyautogui and cv2
pyautogui_stub = types.SimpleNamespace(moveTo=lambda *a, **k: None, click=lambda *a, **k: None, PAUSE=0)
sys.modules.setdefault("pyautogui", pyautogui_stub)
cv2_stub = types.ModuleType("cv2")
cv2_stub.TM_CCOEFF_NORMED = 5
sys.modules.setdefault("cv2", cv2_stub)

from agent.game_state import GameState
from agent.loot import LootCollector
from agent.detector import Detection
from agent.template_matcher import TemplateMatch


class DummyWin:
    region = (0, 0, 100, 100)

    def focus(self):
        pass

    def is_foreground(self):
        return True


class DummyDetector:
    def infer(self, frame):
        return [Detection(name="loot", bbox=[10, 10, 20, 20], conf=0.9)]


class DummyMatcher:
    def find_all(self, frame, name, *a, **k):
        return [TemplateMatch(rect=(30, 30, 5, 5), center=(32, 32), score=0.95)]


def test_collect_updates_inventory_from_detector(monkeypatch):
    clicks = []
    monkeypatch.setattr("agent.loot.click_bbox_center", lambda bbox, region, win=None, rate_limit=True, button="left": (clicks.append(bbox), True)[1])
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    state = GameState(inventory_slots=5)
    collector = LootCollector(detector=DummyDetector(), win=DummyWin(), state=state)
    collected = collector.collect(frame)
    assert collected == 1
    assert state.inventory_occupied == 1
    assert state.inventory_free == 4
    assert clicks == [(10, 10, 20, 20)]


def test_collect_uses_template_matcher(monkeypatch):
    clicks = []
    monkeypatch.setattr("agent.loot.click_bbox_center", lambda bbox, region, win=None, rate_limit=True, button="left": (clicks.append(bbox), True)[1])
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    state = GameState(inventory_slots=5)
    collector = LootCollector(matcher=DummyMatcher(), win=DummyWin(), state=state)
    collected = collector.collect(frame)
    assert collected == 1
    assert state.inventory_occupied == 1
    assert state.inventory_free == 4
    assert clicks == [(30, 30, 35, 35)]
