import os
import sys
import types
import logging
from unittest.mock import Mock, patch

# Make repository root importable and stub optional dependency
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

import agent.wasd as wasd


def _make_user32():
    return types.SimpleNamespace(SendInput=Mock())


def test_send_scan_logs_warning_on_false_return(caplog):
    """No fallback to ``SendInput`` should occur when pydirectinput returns False."""

    user32 = _make_user32()
    kd = Mock(return_value=False)
    kd.__name__ = "keyDown"
    fake_pd = types.SimpleNamespace(keyDown=kd)
    scan = wasd.SCANCODES["w"]
    with patch.object(wasd, "pydirectinput", fake_pd), patch.object(
        wasd, "_user32", user32
    ):
        with caplog.at_level(logging.WARNING):
            wasd._send_scan(scan)
    fake_pd.keyDown.assert_called_once_with("w", _pause=False)
    user32.SendInput.assert_not_called()
    assert any("pydirectinput.keyDown" in r.message for r in caplog.records)


def test_send_scan_logs_warning_on_exception(caplog):
    """Exceptions from pydirectinput should be logged without fallback."""

    user32 = _make_user32()
    ku = Mock(side_effect=RuntimeError("boom"))
    ku.__name__ = "keyUp"
    fake_pd = types.SimpleNamespace(keyUp=ku)
    scan = wasd.SCANCODES["w"]
    with patch.object(wasd, "pydirectinput", fake_pd), patch.object(
        wasd, "_user32", user32
    ):
        with caplog.at_level(logging.WARNING):
            wasd._send_scan(scan, keyup=True)
    fake_pd.keyUp.assert_called_once_with("w", _pause=False)
    user32.SendInput.assert_not_called()
    assert any("pydirectinput.keyUp" in r.message for r in caplog.records)
