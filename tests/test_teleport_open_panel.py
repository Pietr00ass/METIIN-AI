import os
import sys
import types
from pathlib import Path

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

# Stub easyocr to avoid heavy import
sys.modules.setdefault("easyocr", types.SimpleNamespace(Reader=lambda *a, **k: None))

# Provide a minimal numpy stub for imports
sys.modules.setdefault("numpy", types.ModuleType("numpy"))

# Stub PIL.Image used for saving screenshots
PIL_stub = types.ModuleType("PIL")
PIL_stub.Image = types.SimpleNamespace()
sys.modules.setdefault("PIL", PIL_stub)

# Stub pyautogui to avoid real key presses
pyautogui_stub = types.SimpleNamespace(
    moveTo=lambda *a, **k: None,
    click=lambda *a, **k: None,
    press=lambda *a, **k: None,
    locateOnScreen=lambda *a, **k: None,
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

# Stub agent.template_matcher used during import
tm_stub = types.ModuleType("agent.template_matcher")

class _TM:
    def __init__(self, *a, **k):
        pass

tm_stub.TemplateMatcher = _TM
sys.modules.setdefault("agent.template_matcher", tm_stub)

sys.modules.pop("agent.teleport", None)
from agent.teleport import Teleporter


def test_open_panel_detects_non_first_page():
    teleporter = Teleporter.__new__(Teleporter)
    teleporter.dry = False
    hotkey_calls: list[tuple[list[str], float]] = []

    def _hotkey(keys, duration=0.05):
        hotkey_calls.append((keys, duration))

    teleporter.keys = types.SimpleNamespace(hotkey=_hotkey)
    teleporter.open_panel_delay = 0
    teleporter.page_thresh = 0.5
    teleporter.win = types.SimpleNamespace(
        focus=lambda: None,
        is_foreground=lambda: True,
        region=(0, 0, 100, 100),
    )
    teleporter._frame = lambda: types.SimpleNamespace(shape=(1, 1, 3))

    call_order = []

    class TM:
        dir = Path(".")

        def find(self, frame, name, thresh, roi, multi_scale):
            call_order.append(name)
            if name == "strona_II":
                return object()
            return None

    teleporter.tm = TM()

    assert teleporter.open_panel() is True
    assert hotkey_calls == [(["ctrl", "x"], 0.05)]
    assert call_order[:2] == ["strona_I", "strona_II"]
