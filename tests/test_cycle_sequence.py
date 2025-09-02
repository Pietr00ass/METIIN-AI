import numpy as np


def test_cycle_sequence(monkeypatch):
    import types
    import sys
    from pathlib import Path

    # Stub optional dependencies before importing agent modules.
    sys.modules.setdefault("ultralytics", types.SimpleNamespace(YOLO=object))
    sys.modules.setdefault("pyautogui", types.SimpleNamespace(PAUSE=0))
    sys.modules.setdefault("mss", types.SimpleNamespace(mss=lambda: None))
    sys.modules.setdefault("pygetwindow", types.SimpleNamespace(getAllWindows=lambda: []))
    sys.modules.setdefault("win32con", types.SimpleNamespace())
    sys.modules.setdefault("win32gui", types.SimpleNamespace())
    sys.modules.setdefault(
        "cv2", types.SimpleNamespace(TM_CCOEFF_NORMED=0, setNumThreads=lambda n: None)
    )
    sys.modules.setdefault("easyocr", types.SimpleNamespace())
    pil = types.ModuleType("PIL")
    pil_image = types.ModuleType("PIL.Image")
    pil.Image = pil_image
    sys.modules.setdefault("PIL", pil)
    sys.modules.setdefault("PIL.Image", pil_image)

    # Ensure repository root is on sys.path when running standalone
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    from agent.cycle import CycleFarm

    calls = []

    class DummyWindow:
        def __init__(self, title):
            pass

        def locate(self, timeout=0):
            return True

        def grab(self):
            return np.zeros((1, 1, 3), dtype=np.uint8)

        def close(self):
            pass

    class DummyTeleporter:
        def __init__(self, *a, **k):
            pass

        def teleport_slot(self, slot, page_label):
            calls.append(("tp", slot, page_label))

    class DummyChannelSwitcher:
        def __init__(self, *a, **k):
            pass

        def switch(self, ch, post_wait=0):
            calls.append(("ch", ch))

    class DummyKeyHold:
        def __init__(self, *a, **k):
            pass

        def stop(self):
            pass

    class DummyHuntDestroy:
        def __init__(self, cfg, win):
            pass

        def step(self):
            pass

    class DummyDetector:
        def __init__(self, *a, **k):
            pass

        def infer(self, frame):
            return []

    monkeypatch.setattr("agent.cycle.WindowCapture", DummyWindow)
    monkeypatch.setattr("agent.cycle.Teleporter", DummyTeleporter)
    monkeypatch.setattr("agent.cycle.ChannelSwitcher", DummyChannelSwitcher)
    monkeypatch.setattr("agent.cycle.KeyHold", DummyKeyHold)
    monkeypatch.setattr("agent.cycle.ObjectDetector", DummyDetector)
    monkeypatch.setattr("agent.cycle.load_strategy", lambda cfg, win: DummyHuntDestroy(cfg, win))

    cfg = {
        "window": {"title_substr": "x"},
        "paths": {"templates_dir": "", "model": ""},
        "detector": {"classes": []},
        "scan": {"enabled": False},
        "cooldowns": {"slot_min": 0},
    }
    cf = CycleFarm(cfg)
    cf._any_target_seen = lambda: False
    seq = [
        {"ch": 1, "slot": 1},
        {"ch": 2, "slot": 3},
        {"ch": 2, "slot": 4},
        {"ch": 1, "slot": 2},
    ]
    cf.run(
        page_label="P",
        ch_from=1,
        ch_to=2,
        slots=[1, 2],
        per_spot_sec=0,
        clear_sec=0,
        sequence=seq,
    )

    switches = [c[1] for c in calls if c[0] == "ch"]
    teleports = [c[1] for c in calls if c[0] == "tp"]
    assert switches == [1, 2, 1]
    assert teleports == [1, 3, 4, 2]
