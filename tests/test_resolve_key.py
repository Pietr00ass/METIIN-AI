import os
import sys

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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


def test_resolve_key_key_prefix():
    assert wasd.resolve_key("Key.space") == "space"
