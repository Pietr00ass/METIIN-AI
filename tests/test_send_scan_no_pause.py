import os
import sys
import time
import types
from unittest.mock import patch

# Make repository root importable and stub optional dependency
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

import agent.wasd as wasd


def test_send_scan_no_pause_between_events():
    calls = []

    def keyDown(key, _pause=True):
        if _pause:
            time.sleep(0.1)
        calls.append(time.perf_counter())

    def keyUp(key, _pause=True):
        if _pause:
            time.sleep(0.1)
        calls.append(time.perf_counter())

    fake_pd = types.SimpleNamespace(keyDown=keyDown, keyUp=keyUp)
    scan = wasd.SCANCODES["w"]
    with patch.object(wasd, "pydirectinput", fake_pd):
        wasd._send_scan(scan)
        wasd._send_scan(scan, keyup=True)
    assert calls[1] - calls[0] < 0.05
