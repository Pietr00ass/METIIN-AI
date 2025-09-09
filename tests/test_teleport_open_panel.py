import os
import sys
import types

# Ensure repository root on path and stub optional dependencies
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub yaml so configuration loading succeeds without dependency
yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

# Minimal pydantic stub providing BaseModel and Field
_pydantic = types.ModuleType("pydantic")


class _BaseModel:  # pragma: no cover - simple stub
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _Field(default=None, default_factory=None, **kwargs):  # pragma: no cover
    if default_factory is not None:
        return default_factory()
    return default


_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
sys.modules.setdefault("pydantic", _pydantic)

# Stub easyocr and numpy to avoid heavy imports
sys.modules.setdefault("easyocr", types.SimpleNamespace(Reader=lambda *a, **k: None))
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


class WindowCapture:  # pragma: no cover - minimal stub
    pass


wc_mod.WindowCapture = WindowCapture
recorder_pkg.window_capture = wc_mod
sys.modules.setdefault("recorder", recorder_pkg)
sys.modules.setdefault("recorder.window_capture", wc_mod)

# Stub agent.template_matcher used during import
tm_stub = types.ModuleType("agent.template_matcher")


class _TM:  # pragma: no cover - minimal stub
    def __init__(self, *a, **k):
        pass


tm_stub.TemplateMatcher = _TM
sys.modules.setdefault("agent.template_matcher", tm_stub)

sys.modules.pop("agent.teleport", None)
from agent.teleport import Teleporter


def test_open_panel_sends_hotkey_and_returns_true():
    teleporter = Teleporter.__new__(Teleporter)
    teleporter.dry = False
    calls: list[tuple[list[str], float]] = []

    def _hotkey(keys, duration=0.05):
        calls.append((keys, duration))

    teleporter.keys = types.SimpleNamespace(hotkey=_hotkey)
    teleporter.open_panel_delay = 0
    teleporter.win = types.SimpleNamespace(
        focus=lambda: None,
        is_foreground=lambda: True,
    )

    assert teleporter.open_panel() is True
    assert calls == [(["ctrl", "x"], 0.05)]


def test_open_panel_returns_false_when_not_foreground():
    teleporter = Teleporter.__new__(Teleporter)
    teleporter.dry = False
    teleporter.keys = types.SimpleNamespace(hotkey=lambda *a, **k: None)
    teleporter.open_panel_delay = 0
    teleporter.win = types.SimpleNamespace(
        focus=lambda: None,
        is_foreground=lambda: False,
    )

    assert teleporter.open_panel() is False

