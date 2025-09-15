import os
import sys
import types
import numpy as np

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub heavy modules
cv2_stub = types.ModuleType("cv2")
cv2_stub.setNumThreads = lambda n: None
cv2_stub.TM_CCOEFF_NORMED = 5
cv2_stub.COLOR_BGR2GRAY = 0
cv2_stub.cvtColor = lambda frame, code: frame[..., 0]
sys.modules.setdefault("cv2", cv2_stub)

teleport_mod = types.ModuleType("agent.teleport")
class _DummyTeleporter:
    def __init__(self, *a, **k):
        pass
teleport_mod.Teleporter = _DummyTeleporter
sys.modules.setdefault("agent.teleport", teleport_mod)

channel_mod = types.ModuleType("agent.channel")
class _DummyChannelSwitcher:
    def __init__(self, *a, **k):
        pass
channel_mod.ChannelSwitcher = _DummyChannelSwitcher
sys.modules.setdefault("agent.channel", channel_mod)

import agent.hunt_destroy as hd

hd.parse_message = lambda frame: ("", None)
hd.ObjectDetector = lambda *a, **k: None
hd.CollisionAvoid = lambda: types.SimpleNamespace(steer=lambda f: None)
hd.pick_target = lambda *a, **k: None
hd.click_bbox_center = lambda *a, **k: None

class _StubKeyHold:
    def __init__(self, dry=False, active_fn=None):
        self.pressed = []
        self.released = []
        self.down = set()
        self.lock = __import__("threading").Lock()
    def press(self, key):
        with self.lock:
            if key not in self.down:
                self.down.add(key)
                self.pressed.append(key)
    def release(self, key):
        with self.lock:
            if key in self.down:
                self.down.remove(key)
                self.released.append(key)
    def release_all(self):
        with self.lock:
            for k in list(self.down):
                self.down.remove(k)
                self.released.append(k)
    def stop(self):
        pass

class _DummyWin:
    region = (0, 0, 100, 100)
    def grab(self):
        return np.zeros((100, 100, 3), dtype=np.uint8)
    def is_foreground(self):
        return True


def test_stuck_recovery(monkeypatch):
    class _FlowStub:
        def __init__(self, *a, **k):
            self.reset_called = False
        def update(self, frame):
            return True
        def reset(self):
            self.reset_called = True

    monkeypatch.setattr(hd, "FlowStuck", _FlowStub)
    monkeypatch.setattr(hd, "KeyHold", _StubKeyHold)
    monkeypatch.setattr(hd.time, "sleep", lambda s: None)
    cfg = {
        "paths": {"model": "", "templates_dir": ""},
        "detector": {"classes": [], "conf_thr": 0.5, "iou_thr": 0.5},
        "dry_run": True,
        "stuck": {"window": 0.1, "min_mag": 0.0, "recovery_action": "rotate"},
    }
    agent = hd.HuntDestroy(cfg, _DummyWin())
    agent.step()
    assert "e" in agent.keys.pressed
    assert agent.flow.reset_called
