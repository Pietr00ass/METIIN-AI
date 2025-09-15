"""Configuration loader for the Metin2 agent using Pydantic models."""

from __future__ import annotations

from pathlib import Path
import types

from config.models import AgentConfig, TeleportSlot

try:  # yaml is optional for tests
    import yaml
except Exception:  # pragma: no cover - provide dummy fallback
    yaml = types.SimpleNamespace(safe_load=lambda f: {})

_cfg: AgentConfig | None = None


def load_config(path: str | Path = "config/agent.yaml") -> AgentConfig:
    """Load configuration file into :class:`AgentConfig`."""

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    return AgentConfig(**data)


def get_config(path: str | Path = "config/agent.yaml") -> AgentConfig:
    """Return cached :class:`AgentConfig` instance."""

    global _cfg
    if _cfg is None:
        _cfg = load_config(path)
    return _cfg


def reload_config(path: str | Path = "config/agent.yaml") -> AgentConfig:
    """Reload configuration file and update the cached instance."""

    global _cfg
    _cfg = load_config(path)
    return _cfg


__all__ = ["get_config", "load_config", "reload_config", "AgentConfig", "TeleportSlot"]
