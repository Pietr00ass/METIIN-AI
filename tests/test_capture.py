import os
import sys
import types
from unittest.mock import patch

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub heavy optional dependencies so recorder.capture can be imported
sys.modules.setdefault("cv2", types.ModuleType("cv2"))
sys.modules.setdefault("mss", types.ModuleType("mss"))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
stub_pynput = types.ModuleType("pynput")


class DummyListener:
    def __init__(self, *a, **k):
        pass

    def start(self):
        pass

    def stop(self):
        pass


stub_pynput.mouse = types.SimpleNamespace(Listener=DummyListener)
sys.modules.setdefault("pynput", stub_pynput)
sys.modules.setdefault("pynput.mouse", stub_pynput.mouse)

from recorder.capture import InputLogger


def test_keyboard_hook_records_scancodes():
    events = []

    def fake_hook(cb):
        fake_hook.cb = cb
        return object()

    stub_keyboard = types.SimpleNamespace(hook=fake_hook, unhook=lambda h: None)

    with patch("recorder.capture._keyboard", stub_keyboard):
        logger = InputLogger()
        logger.start()

        class E:
            def __init__(self, sc, et):
                self.scan_code = sc
                self.event_type = et

        fake_hook.cb(E(30, "down"))
        fake_hook.cb(E(30, "up"))
        logger.stop()
        events = logger.flush()

    assert events[0][2] == {"scancode": 30, "down": True}
    assert events[1][2] == {"scancode": 30, "down": False}
