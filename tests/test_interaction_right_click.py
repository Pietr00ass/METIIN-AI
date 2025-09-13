from types import SimpleNamespace

import numpy as np

import agent.interaction as inter


def test_right_click_bbox_center(monkeypatch):
    clicks = []
    monkeypatch.setattr(inter.pyautogui, "moveTo", lambda *a, **k: None)
    monkeypatch.setattr(
        inter.pyautogui,
        "click",
        lambda *a, **k: clicks.append(k.get("button", "left")),
    )
    assert inter.right_click_bbox_center((0, 0, 10, 10), (0, 0, 100, 100))
    assert clicks == ["right"]


def test_detect_and_right_click(monkeypatch):
    clicks = []
    monkeypatch.setattr(inter.pyautogui, "moveTo", lambda *a, **k: None)
    monkeypatch.setattr(
        inter.pyautogui,
        "click",
        lambda *a, **k: clicks.append(k.get("button", "left")),
    )

    class DummyDetector:
        def infer(self, frame):
            return [SimpleNamespace(name="item", bbox=(0, 0, 10, 10))]

    region = (0, 0, 100, 100)
    frame = object()
    assert inter.detect_and_right_click(
        DummyDetector(),
        region,
        frame=frame,
        target_names=["item"],
        rate_limit=False,
    )
    assert clicks == ["right"]


def test_detect_and_right_click_grabs_frame(monkeypatch):
    clicks = []
    monkeypatch.setattr(inter.pyautogui, "moveTo", lambda *a, **k: None)
    monkeypatch.setattr(
        inter.pyautogui,
        "click",
        lambda *a, **k: clicks.append(k.get("button", "left")),
    )

    class DummyDetector:
        def infer(self, frame):
            assert isinstance(frame, np.ndarray)
            return [SimpleNamespace(name="item", bbox=(0, 0, 10, 10))]

    class DummyWin:
        def grab(self):
            return np.zeros((1, 1, 3), dtype=np.uint8)

        def focus(self):
            pass

        def is_foreground(self):
            return True

    region = (0, 0, 100, 100)
    assert inter.detect_and_right_click(
        DummyDetector(),
        region,
        target_names=["item"],
        win=DummyWin(),
        rate_limit=False,
    )
    assert clicks == ["right"]
