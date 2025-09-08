import logging
import os
import sys
import types
import numpy as np

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out optional dependencies used during import
sys.modules.setdefault("mss", types.SimpleNamespace(mss=lambda: types.SimpleNamespace(close=lambda: None)))
sys.modules.setdefault("pygetwindow", types.SimpleNamespace(getAllWindows=lambda: []))

from agent_rl.metin2_env import Metin2Env


def test_detect_monsters_logs_exception(caplog):
    env = Metin2Env(dry=True)

    class Boom:
        def infer(self, frame):  # pragma: no cover - raising intentionally
            raise RuntimeError("boom")

    env.detector = Boom()  # type: ignore
    frame = np.zeros((1, 1, 3), dtype=np.uint8)

    caplog.set_level(logging.ERROR)
    assert env._detect_monsters(frame) == []
    assert "Detector inference failed" in caplog.text
