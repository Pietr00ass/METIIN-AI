import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agent.buff_manager as bm


class DummyKeys:
    def __init__(self):
        self.tapped = []

    def tap(self, key: str) -> None:
        self.tapped.append(key)


def test_buff_manager_press(monkeypatch):
    t = 0.0

    def fake_time():
        return t

    monkeypatch.setattr(bm.time, "monotonic", fake_time)
    keys = DummyKeys()
    buff = bm.Buff("a", 1.0)
    mgr = bm.BuffManager(keys, [buff])

    mgr.step()
    assert keys.tapped == ["a"]

    mgr.step()
    assert keys.tapped == ["a"]

    t = 1.1
    mgr.step()
    assert keys.tapped == ["a", "a"]


def test_buff_manager_respects_active(monkeypatch):
    t = 0.0

    def fake_time():
        return t

    monkeypatch.setattr(bm.time, "monotonic", fake_time)
    keys = DummyKeys()
    active = True

    def is_active():
        return active

    buff = bm.Buff("b", 1.0, is_active=is_active)
    mgr = bm.BuffManager(keys, [buff])

    mgr.step()
    assert keys.tapped == []

    t = 0.5
    mgr.step()
    assert keys.tapped == []

    active = False
    t = 0.6
    mgr.step()
    assert keys.tapped == ["b"]

    t = 1.5
    mgr.step()
    assert keys.tapped == ["b"]

    t = 1.7
    mgr.step()
    assert keys.tapped == ["b", "b"]
