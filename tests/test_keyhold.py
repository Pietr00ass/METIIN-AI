import os
import sys
import types
from unittest.mock import call, patch

import pytest

# Make repository root importable and provide a stub ``yaml`` module so that the
# :mod:`agent` package can be imported without optional dependencies.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

_pydantic = types.ModuleType("pydantic")


class _BaseModel:
    pass


def _Field(*args, **kwargs):  # noqa: D401 - simple stub
    return None


_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
sys.modules.setdefault("pydantic", _pydantic)

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


def test_press_release_handles_uppercase():
    """Uppercase keys should be normalized to lowercase scancodes."""

    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("W")
        kh.release("W")
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES["w"])
    mock_up.assert_called_once_with(wasd.SCANCODES["w"])


@pytest.mark.parametrize("key", ["up", "down", "left", "right"])
def test_press_release_arrow_calls_sendinput_with_extended(key):
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press(key)
        kh.release(key)
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES[key], extended=True)
    mock_up.assert_called_once_with(wasd.SCANCODES[key], extended=True)


def test_press_skipped_when_window_inactive():
    """active_fn returning False should suppress key presses."""

    with patch.object(wasd, "key_down") as mock_down:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: False)
        kh.press("w")
        kh.stop()

    mock_down.assert_not_called()


def test_press_release_e_calls_sendinput_when_active():
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("e")
        kh.release("e")
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES["e"])
    mock_up.assert_called_once_with(wasd.SCANCODES["e"])


@pytest.mark.parametrize("num", list("12345678"))
def test_ctrl_number_combo(num):
    """Ctrl+1..8 should send expected scan codes."""

    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("ctrl")
        kh.press(num)
        kh.release(num)
        kh.release("ctrl")
        kh.stop()

    sc_ctrl = wasd.SCANCODES["ctrl"]
    sc_num = wasd.SCANCODES[num]
    assert mock_down.call_args_list == [call(sc_ctrl), call(sc_num)]
    assert mock_up.call_args_list == [call(sc_num), call(sc_ctrl)]


@pytest.mark.parametrize("key", [f"numpad{i}" for i in range(1, 9)])
def test_press_release_numpad_calls_sendinput(key):
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press(key)
        kh.release(key)
        kh.stop()

    mock_down.assert_called_once_with(wasd.SCANCODES[key])
    mock_up.assert_called_once_with(wasd.SCANCODES[key])


def test_ctrl_x_combo():
    """Ctrl+X hotkey should be emitted correctly."""

    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up:
        kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
        kh.press("ctrl")
        kh.press("x")
        kh.release("x")
        kh.release("ctrl")
        kh.stop()

    sc_ctrl = wasd.SCANCODES["ctrl"]
    sc_x = wasd.SCANCODES["x"]
    assert mock_down.call_args_list == [call(sc_ctrl), call(sc_x)]
    assert mock_up.call_args_list == [call(sc_x), call(sc_ctrl)]



@pytest.mark.parametrize("num", list("12345678"))
def test_hotkey_ctrl_number_combo(num):
    """Hotkey should handle Ctrl+1..8 combinations with a delay."""

    kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
    kh.stop()
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up, patch.object(wasd.time, "sleep", return_value=None) as mock_sleep:
        kh.hotkey(["ctrl", num], duration=0.1)

    sc_ctrl = wasd.SCANCODES["ctrl"]
    sc_num = wasd.SCANCODES[num]
    assert mock_down.call_args_list == [call(sc_ctrl), call(sc_num)]
    assert mock_sleep.call_args_list == [call(0.1)]
    assert mock_up.call_args_list == [call(sc_num), call(sc_ctrl)]


@pytest.mark.parametrize("num", [f"numpad{i}" for i in range(1, 9)])
def test_hotkey_ctrl_numpad_combo(num):
    """Hotkey should handle Ctrl+NumPad1..8 combinations with a delay."""

    kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
    kh.stop()
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up, patch.object(wasd.time, "sleep", return_value=None) as mock_sleep:
        kh.hotkey(["ctrl", num], duration=0.1)

    sc_ctrl = wasd.SCANCODES["ctrl"]
    sc_num = wasd.SCANCODES[num]
    assert mock_down.call_args_list == [call(sc_ctrl), call(sc_num)]
    assert mock_sleep.call_args_list == [call(0.1)]
    assert mock_up.call_args_list == [call(sc_num), call(sc_ctrl)]


@pytest.mark.parametrize("key", [f"numpad{i}" for i in range(1, 9)])
def test_hotkey_single_numpad(key):
    """Hotkey should handle single NumPad keys with a delay."""

    kh = wasd.KeyHold(dry=False, active_fn=lambda: True)
    kh.stop()
    with patch.object(wasd, "key_down") as mock_down, patch.object(
        wasd, "key_up"
    ) as mock_up, patch.object(wasd.time, "sleep", return_value=None) as mock_sleep:
        kh.hotkey([key], duration=0.1)

    sc = wasd.SCANCODES[key]
    assert mock_down.call_args_list == [call(sc)]
    assert mock_sleep.call_args_list == [call(0.1)]
    assert mock_up.call_args_list == [call(sc)]