import os
import sys
import types
from unittest.mock import patch


# Make repository root importable and provide a stub ``yaml`` module so that the
# :mod:`agent` package can be imported without optional dependencies.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.modules.setdefault("yaml", types.ModuleType("yaml"))

import agent.wasd as wasd


def test_dry_mode_skips_sendinput():
    """No SendInput calls should be made when dry mode is enabled."""

    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=True, active_fn=lambda: True)
        kh.press("w")
        kh.release("w")
        kh.release_all()
        kh.stop()

    assert mock_down.call_count == 0
    assert mock_up.call_count == 0


def test_press_release_calls_sendinput_when_active():
    """In active mode the helper functions should be invoked."""

    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("w")
        kh.release("w")
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES["w"])
    mock_up.assert_called_once_with(wasd.SCANCODES["w"])


def test_press_release_i_calls_sendinput_when_active():
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("i")
        kh.release("i")
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES["i"])
    mock_up.assert_called_once_with(wasd.SCANCODES["i"])


def test_press_skipped_when_window_inactive():
    """active_fn returning False should suppress key presses."""

    with patch.object(wasd, "key_down") as mock_down:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: False)
        kh.press("w")
        kh.stop()

    mock_down.assert_not_called()

