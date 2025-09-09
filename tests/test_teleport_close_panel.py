import os
import sys
import types
from unittest.mock import Mock

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub yaml so configuration loading succeeds without dependency
yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

# Minimal pydantic stub providing BaseModel and Field
_pydantic = types.ModuleType("pydantic")

class _BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def _Field(default=None, default_factory=None, **kwargs):
    if default_factory is not None:
        return default_factory()
    return default

_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
sys.modules.setdefault("pydantic", _pydantic)

# Stub pyautogui to avoid real key presses
pyautogui_stub = types.SimpleNamespace(
    moveTo=lambda *a, **k: None,
    click=lambda *a, **k: None,
    press=lambda *a, **k: None,
    PAUSE=0,
)
sys.modules.setdefault("pyautogui", pyautogui_stub)

# Stub recorder.window_capture
recorder_pkg = types.ModuleType("recorder")
recorder_pkg.__path__ = []
wc_mod = types.ModuleType("recorder.window_capture")

class WindowCapture:
    pass

wc_mod.WindowCapture = WindowCapture
recorder_pkg.window_capture = wc_mod
sys.modules.setdefault("recorder", recorder_pkg)
sys.modules.setdefault("recorder.window_capture", wc_mod)

sys.modules.pop("agent.teleport", None)
from agent.teleport import Teleporter


def test_close_panel_taps_esc_on_keys():
    teleporter = Teleporter.__new__(Teleporter)
    teleporter.dry = False
    mock_keys = Mock()
    teleporter.keys = mock_keys

    teleporter.close_panel()

    mock_keys.tap.assert_called_once_with("esc")
