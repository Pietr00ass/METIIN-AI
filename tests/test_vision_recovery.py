import os
import sys
import types

# Make repository root importable and stub heavy optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)


class _Logger:
    def __getattr__(self, name):
        return lambda *a, **k: None


sys.modules.setdefault("loguru", types.SimpleNamespace(logger=_Logger()))

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

import agent.vision as vision
import agent.dungeon_polana as dp


class DummyWin:
    region = (0, 0, 100, 100)

    def __init__(self, frame):
        self._frame = frame

    def grab(self):
        return self._frame

    def is_foreground(self):
        return True


class DummyTeleporter:
    def __init__(self, *a, **k):
        pass

    def teleport_slot(self, slot, page_label=None):
        pass


class DummyDetector:
    def __init__(self, *a, **k):
        pass

    def infer(self, frame):
        return []


class DummyKeys:
    def __init__(self, dry=False, active_fn=None):
        pass

    def release_all(self):
        pass

    def stop(self):
        pass


def _cfg():
    return types.SimpleNamespace(
        paths=types.SimpleNamespace(model="", templates_dir=""),
        detector=types.SimpleNamespace(
            classes=[], conf_thr=0.5, iou_thr=0.5, cv2_threads=0
        ),
        dungeon_polana=types.SimpleNamespace(
            teleport_slot=1, boss_timeout=1, error_timeout=1
        ),
        dry_run=True,
    )


def _make_frame(template):
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    h, w = template.shape
    frame[:h, :w, 0] = template
    return frame


def test_templates_detect_states():
    f_logout = _make_frame(vision.LOGGED_OUT_TEMPLATE)
    f_loading = _make_frame(vision.LOADING_TEMPLATE)
    assert vision.is_logged_out(f_logout)
    assert not vision.is_logged_out(f_loading)
    assert vision.is_loading(f_loading)
    assert not vision.is_loading(f_logout)


def test_strategy_triggers_recovery(monkeypatch):
    monkeypatch.setattr(dp, "ObjectDetector", DummyDetector)
    monkeypatch.setattr(dp, "Teleporter", lambda *a, **k: DummyTeleporter())
    monkeypatch.setattr(dp, "KeyHold", DummyKeys)
    monkeypatch.setattr(dp, "parse_message", lambda frame: ("", None))

    calls: list[str] = []
    dp.controller = types.SimpleNamespace(
        restart_game=lambda: calls.append("restart"),
        ensure_logged_in=lambda: calls.append("ensure"),
    )

    agent = dp.DungeonPolana(_cfg(), DummyWin(_make_frame(vision.LOGGED_OUT_TEMPLATE)))
    agent.step()
    assert calls == ["restart"]

    calls.clear()
    agent = dp.DungeonPolana(_cfg(), DummyWin(_make_frame(vision.LOADING_TEMPLATE)))
    agent.step()
    assert calls == ["ensure"]
