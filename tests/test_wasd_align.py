import os
import sys
import types
import json
from unittest.mock import patch

# Make repository root importable and stub optional modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
cv2_stub = types.SimpleNamespace(CAP_PROP_FPS=0)
sys.modules.setdefault("cv2", cv2_stub)

# Ensure the real numpy package is used even if previous tests stubbed it
sys.modules.pop("numpy", None)
import numpy as np
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
import agent.wasd as wasd
from recorder import align_wasd


def test_resolve_key_strips_prefix():
    assert wasd.resolve_key("Key.space") == "space"
    assert wasd.resolve_key("w") == "w"


def test_align_ignores_non_wasd_keys(tmp_path):
    events = [
        {"ts": 0.05, "kind": "key", "payload": {"key": "space", "down": True}},
        {"ts": 0.06, "kind": "key", "payload": {"key": "space", "down": False}},
        {"ts": 0.25, "kind": "key", "payload": {"scancode": 17, "down": True}},
        {"ts": 0.35, "kind": "key", "payload": {"scancode": 17, "down": False}},
    ]
    events_path = tmp_path / "events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    video_path = tmp_path / "video.mp4"

    frames = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)]

    class DummyCap:
        def __init__(self, frames):
            self.frames = frames
            self.idx = 0

        def get(self, prop):
            return 10.0  # fps

        def read(self):
            if self.idx < len(self.frames):
                frame = self.frames[self.idx]
                self.idx += 1
                return True, frame
            return False, None

        def release(self):
            pass

    def dummy_resize(frame, size):
        return frame

    saved = []

    with patch.object(align_wasd.cv2, "CAP_PROP_FPS", 0, create=True), \
         patch.object(align_wasd.cv2, "VideoCapture", lambda path: DummyCap(frames), create=True), \
         patch.object(align_wasd.cv2, "resize", dummy_resize, create=True), \
         patch.object(align_wasd.np, "savez_compressed", lambda path, img=None, y=None: saved.append(y)):
        align_wasd.align(str(video_path), str(events_path), tmp_path)

    assert [y.tolist() for y in saved] == [
        [0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
    ]
