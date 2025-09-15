import os
import sys
import types
from types import SimpleNamespace
import pytest

# Make repository root importable and stub optional deps
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda f: {}
sys.modules.setdefault("yaml", yaml_stub)

_pydantic = types.ModuleType("pydantic")
class _BaseModel:
    pass

def _Field(*args, **kwargs):
    return None
_pydantic.BaseModel = _BaseModel
_pydantic.Field = _Field
sys.modules.setdefault("pydantic", _pydantic)

import utils.humanizer as humanizer
import agent.wasd as wasd


def test_random_pause_range(monkeypatch):
    """random_pause should sleep within base ± jitter."""
    called = {}
    monkeypatch.setattr(humanizer.time, "sleep", lambda d: called.setdefault("d", d))
    monkeypatch.setattr(humanizer.random, "uniform", lambda a, b: b)
    cfg = SimpleNamespace(humanizer=SimpleNamespace(pause_jitter=0.1))
    monkeypatch.setattr(humanizer, "get_config", lambda: cfg)
    humanizer.random_pause(1.0)
    assert pytest.approx(1.1) == called["d"]
    monkeypatch.setattr(humanizer.random, "uniform", lambda a, b: a)
    called.clear()
    humanizer.random_pause(1.0)
    assert pytest.approx(0.9) == called["d"]


def test_jitter_move_range(monkeypatch):
    """jitter_move should return values within ±max_jitter."""
    monkeypatch.setattr(humanizer.random, "uniform", lambda a, b: b)
    x, y = humanizer.jitter_move(10, 20, 5)
    assert (x, y) == (15, 25)
    monkeypatch.setattr(humanizer.random, "uniform", lambda a, b: a)
    x, y = humanizer.jitter_move(10, 20, 5)
    assert (x, y) == (5, 15)


def test_keyhold_tap_uses_random_pause(monkeypatch):
    """KeyHold.tap should invoke random_pause."""
    calls = []
    monkeypatch.setattr(wasd, "random_pause", lambda base: calls.append(base))
    kh = wasd.KeyHold(dry=True, active_fn=lambda: True)
    kh.tap("w")
    kh.stop()
    assert calls == [0]
