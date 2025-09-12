from types import SimpleNamespace
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
    assert inter.detect_and_right_click(
        DummyDetector(), None, region, ["item"], rate_limit=False
    )
    assert clicks == ["right"]
