import os
import sys
import types

# Make repository root importable and provide stub modules so that optional
# dependencies are not required during testing.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
sys.modules.setdefault("cv2", types.ModuleType("cv2"))
sys.modules.setdefault("mss", types.ModuleType("mss"))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
pynput_stub = types.ModuleType("pynput")
pynput_stub.mouse = types.ModuleType("mouse")
pynput_stub.keyboard = types.ModuleType("keyboard")
sys.modules.setdefault("pynput", pynput_stub)
sys.modules.setdefault("pynput.mouse", pynput_stub.mouse)
sys.modules.setdefault("pynput.keyboard", pynput_stub.keyboard)

from recorder.capture import InputLogger


class DummyKey:
    def __init__(self, vk, scan, name="a"):
        self.vk = vk
        self.scan = scan
        self._name = name

    def __str__(self):  # pragma: no cover - trivial
        return self._name


def test_logger_records_scan_and_vk():
    logger = InputLogger()
    key = DummyKey(vk=97, scan=0x1E, name='a')
    logger.on_press(key)
    events = logger.flush()
    assert len(events) == 1
    ts, kind, payload = events[0]
    assert kind == 'key'
    assert payload['key'] == str(key)
    assert payload['down'] is True
    assert payload.get('vk') == key.vk
    assert payload.get('scan') == key.scan
