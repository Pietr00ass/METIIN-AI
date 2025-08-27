import os
import sys
import types
from unittest.mock import patch

# Make repository root importable and provide stubs for optional dependencies.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
for mod in ("cv2", "mss", "numpy"):
    sys.modules.setdefault(mod, types.ModuleType(mod))

# ``pynput`` may be unavailable or fail to initialize on some platforms.
try:
    import pynput  # type: ignore
except Exception:  # pragma: no cover - handled by providing stubs
    pynput = types.ModuleType("pynput")
    pynput.keyboard = types.SimpleNamespace()
    pynput.mouse = types.SimpleNamespace()
    sys.modules.setdefault("pynput", pynput)
    sys.modules.setdefault("pynput.keyboard", pynput.keyboard)
    sys.modules.setdefault("pynput.mouse", pynput.mouse)

from recorder import capture


def test_inputlogger_records_down_up_pairs():
    """InputLogger should capture matching key down/up events with timestamps."""

    logger = capture.InputLogger()

    class DummyListener:
        def __init__(self, on_press=None, on_release=None):
            self.on_press = on_press
            self.on_release = on_release

        def start(self):
            if self.on_press:
                self.on_press("a")
            if self.on_release:
                self.on_release("a")
            return self

        def stop(self):
            pass

    with patch.object(capture.keyboard, "Listener", DummyListener, create=True):
        with patch("time.time", side_effect=[1.0, 2.0]):
            capture.keyboard.Listener(
                on_press=logger.on_press, on_release=logger.on_release
            ).start()

    events = logger.flush()

    assert events == [
        (1.0, "key", {"key": "a", "down": True}),
        (2.0, "key", {"key": "a", "down": False}),
    ]


def test_on_release_includes_scan_vk_codes():
    """on_release should preserve scan and vk codes in the payload."""

    logger = capture.InputLogger()

    class Key:
        def __init__(self, scan, vk):
            self.scan = scan
            self.vk = vk

    # Use known mappings from agent.wasd
    import agent.wasd as wasd

    key = Key(wasd.SCANCODES["a"], wasd.VK_CODES["a"])

    with patch("time.time", return_value=0.0):
        logger.on_release(key)

    events = logger.flush()

    assert events == [
        (
            0.0,
            "key",
            {
                "key": "a",
                "down": False,
                "scan": wasd.SCANCODES["a"],
                "vk": wasd.VK_CODES["a"],
            },
        )
    ]
