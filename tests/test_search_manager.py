import os
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out heavy dependencies required by agent.channel and agent.teleport
teleport_mod = types.ModuleType("agent.teleport")


class _StubTeleporter:
    def __init__(self, *a, **k):
        pass


teleport_mod.Teleporter = _StubTeleporter
sys.modules.setdefault("agent.teleport", teleport_mod)

channel_mod = types.ModuleType("agent.channel")


class _StubChannelSwitcher:
    def __init__(self, *a, **k):
        pass

    def switch(self, *a, **k):
        pass


channel_mod.ChannelSwitcher = _StubChannelSwitcher
sys.modules.setdefault("agent.channel", channel_mod)

from agent.search import SearchManager

class DummyTeleporter:
    def __init__(self):
        self.calls = 0

    def teleport_slot(self, slot, page):
        self.calls += 1


class DummyChannelSwitcher:
    def __init__(self):
        self.switched = []

    def switch(self, ch):
        self.switched.append(ch)


def test_switch_channel_after_configured_teleports():
    teleporter = DummyTeleporter()
    channel = DummyChannelSwitcher()
    # no_target_sec < 0 ensures the teleportation branch is always taken
    manager = SearchManager(
        teleporter,
        channel,
        tp_slots=[1],
        tp_page=None,
        channels=[1, 2],
        no_target_sec=-1,
        channel_every=8,
    )

    # perform 7 teleports - channel should not change yet
    for _ in range(7):
        manager.handle_no_target(True)
    assert channel.switched == []

    # 8th teleport triggers channel switch
    manager.handle_no_target(True)
    assert channel.switched == [1]
