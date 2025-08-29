import os
import sys
import types

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Remove any stubs that other tests might have installed
sys.modules.pop("recorder", None)
sys.modules.pop("recorder.window_capture", None)


class DummySct:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def grab(self, region):
        # minimal object with width/height attributes
        return types.SimpleNamespace(width=1, height=1)


# Stub external dependencies used by WindowCapture
sys.modules.setdefault("pygetwindow", types.SimpleNamespace(getAllWindows=lambda: []))
sys.modules.setdefault("win32con", types.SimpleNamespace())
sys.modules.setdefault("win32gui", types.SimpleNamespace())
sys.modules["mss"] = types.SimpleNamespace(mss=lambda: DummySct())

import recorder.window_capture as wc


def test_close_calls_underlying_close():
    cap = wc.WindowCapture("foo")
    assert isinstance(cap.sct, DummySct)
    cap.close()
    assert cap.sct.closed


def test_context_manager_closes():
    with wc.WindowCapture("foo") as cap:
        assert isinstance(cap.sct, DummySct)
    assert cap.sct.closed
