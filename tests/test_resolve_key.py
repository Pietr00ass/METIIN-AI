import os
import sys

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import agent.wasd as wasd


def test_resolve_key_only_scan():
    sc = wasd.SCANCODES["w"]
    assert wasd.resolve_key({"scan": sc}) == "w"


def test_resolve_key_only_vk():
    vk = wasd.VK_CODES["a"]
    assert wasd.resolve_key({"vk": vk}) == "a"


def test_resolve_key_i_scan_and_vk():
    sc = wasd.SCANCODES["i"]
    vk = wasd.VK_CODES["i"]
    assert wasd.resolve_key({"scan": sc}) == "i"
    assert wasd.resolve_key({"vk": vk}) == "i"


def test_resolve_key_e_scan_and_vk():
    sc = wasd.SCANCODES["e"]
    vk = wasd.VK_CODES["e"]
    assert wasd.resolve_key({"scan": sc}) == "e"
    assert wasd.resolve_key({"vk": vk}) == "e"


def test_resolve_key_key_prefix():
    assert wasd.resolve_key("Key.space") == "space"


@pytest.mark.parametrize("key", ["up", "down", "left", "right"])
def test_resolve_key_arrows(key):
    sc = wasd.SCANCODES[key]
    vk = wasd.VK_CODES[key]
    assert wasd.resolve_key({"scan": sc}) == key
    assert wasd.resolve_key({"vk": vk}) == key
