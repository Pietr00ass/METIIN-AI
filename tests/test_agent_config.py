import os
import sys
import types

import pytest

# Ensure repository root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agent


def test_load_config_missing_file(tmp_path):
    path = tmp_path / "missing.yaml"
    cfg = agent.load_config(path)
    assert isinstance(cfg, agent.AgentConfig)


def test_load_config_reads_yaml(tmp_path, monkeypatch):
    """load_config should parse data from YAML files."""

    cfg_dict = {"controls": {"mouse_pause": 0.1}}
    monkeypatch.setattr(agent, "yaml", types.SimpleNamespace(safe_load=lambda f: cfg_dict))
    path = tmp_path / "cfg.yaml"
    path.write_text("dummy")
    cfg = agent.load_config(path)
    assert cfg.controls.mouse_pause == 0.1


def test_reload_config(tmp_path, monkeypatch):
    """reload_config should update the cached configuration instance."""

    path = tmp_path / "cfg.yaml"
    path.write_text("dummy")
    cfg1 = agent.AgentConfig(controls={"mouse_pause": 0.1})
    cfg2 = agent.AgentConfig(controls={"mouse_pause": 0.2})

    monkeypatch.setattr(agent, "load_config", lambda p: cfg1)
    agent._cfg = None
    cfg = agent.get_config(path)
    assert cfg.controls.mouse_pause == 0.1

    monkeypatch.setattr(agent, "load_config", lambda p: cfg2)
    new_cfg = agent.reload_config(path)
    assert new_cfg.controls.mouse_pause == 0.2
    assert agent.get_config(path).controls.mouse_pause == 0.2
