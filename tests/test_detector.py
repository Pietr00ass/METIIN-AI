import os
import sys
import types
import importlib
from unittest.mock import patch

sys.modules.pop("numpy", None)
np = importlib.import_module("numpy")

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
# Provide minimal cv2 stub so ``cv2.setNumThreads`` is available
sys.modules["cv2"] = types.SimpleNamespace(setNumThreads=lambda *a, **k: None)

# Provide a minimal ultralytics stub so agent.detector can be imported
ultra_stub = types.ModuleType("ultralytics")
class _StubYOLO:
    def __init__(self, *a, **k):
        pass
    def predict(self, *a, **k):
        return []
ultra_stub.YOLO = _StubYOLO
sys.modules.setdefault("ultralytics", ultra_stub)

import agent.detector as detector


class FakeTensor:
    def __init__(self, value):
        self.value = value
    def cpu(self):
        return self
    def numpy(self):
        return np.array(self.value)
    def __getitem__(self, idx):
        return FakeTensor(self.value[idx])
    def __int__(self):
        return int(self.value)


class FakeBox:
    def __init__(self, cls, xyxy, conf):
        self.cls = FakeTensor(cls)
        self.xyxy = FakeTensor([xyxy])
        self.conf = FakeTensor(conf)


class FakeResult:
    def __init__(self):
        self.names = {0: "metin", 1: "boss"}
        self.boxes = [
            FakeBox(0, [10, 20, 30, 40], 0.9),
            FakeBox(1, [50, 60, 70, 80], 0.8),
        ]


def test_infer_filters_classes():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    with patch("agent.detector.YOLO") as MockYOLO:
        model = MockYOLO.return_value
        model.predict.return_value = [FakeResult()]
        det = detector.ObjectDetector("model.pt", classes=["boss"])
        out = det.infer(frame)
    assert out == [{"name": "boss", "bbox": [50.0, 60.0, 70.0, 80.0], "conf": 0.8}]
