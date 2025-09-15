import importlib
import os
import sys
import types

import pytest

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class DummySct:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def grab(self, region):
        return types.SimpleNamespace(width=1, height=1)


def _import_wc(monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setitem(
        sys.modules, "pygetwindow", types.SimpleNamespace(getAllWindows=lambda: [])
    )
    monkeypatch.setitem(sys.modules, "mss", types.SimpleNamespace(mss=lambda: DummySct()))
    if platform == "win32":
        monkeypatch.setitem(sys.modules, "win32con", types.SimpleNamespace())
        monkeypatch.setitem(sys.modules, "win32gui", types.SimpleNamespace())
    else:
        sys.modules.pop("win32con", None)
        sys.modules.pop("win32gui", None)
    sys.modules.pop("recorder", None)
    sys.modules.pop("recorder.window_capture", None)
    wc = importlib.import_module("recorder.window_capture")
    monkeypatch.setitem(sys.modules, "recorder.window_capture", wc)
    monkeypatch.setitem(sys.modules, "recorder", sys.modules["recorder"])
    return wc


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_close_calls_underlying_close(monkeypatch, platform):
    wc = _import_wc(monkeypatch, platform)
    cap = wc.WindowCapture("foo")
    assert isinstance(cap.sct, DummySct)
    cap.close()
    assert cap.sct.closed


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_context_manager_closes(monkeypatch, platform):
    wc = _import_wc(monkeypatch, platform)
    with wc.WindowCapture("foo") as cap:
        assert isinstance(cap.sct, DummySct)
    assert cap.sct.closed


def test_locate_returns_false_when_window_missing(monkeypatch):
    """WindowCapture.locate should return ``False`` if no window is found."""

    wc = _import_wc(monkeypatch, "linux")
    cap = wc.WindowCapture("does-not-exist", poll_sec=0)
    assert cap.locate(timeout=0.01) is False


def test_locate_fallbacks_to_wmctrl(monkeypatch):
    """When ``pygetwindow`` is unusable, ``wmctrl`` fallback should be used."""

    wc = _import_wc(monkeypatch, "linux")
    impl = importlib.import_module(wc.WindowCapture.__module__)

    def _raise():
        raise NotImplementedError

    monkeypatch.setattr(impl.gw, "getAllWindows", _raise)

    fake = types.SimpleNamespace(
        wid="0x1",
        title="metin2",
        left=0,
        top=0,
        width=100,
        height=100,
        isMinimized=False,
        restore=lambda: None,
        activate=lambda: None,
    )
    monkeypatch.setattr(impl, "_wmctrl_windows", lambda: [fake])

    cap = wc.WindowCapture("metin2", poll_sec=0)
    assert cap.locate(timeout=0.01) is True
