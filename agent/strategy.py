from __future__ import annotations

import importlib
from typing import Protocol, Type, Dict, Callable


class AgentStrategy(Protocol):
    """Interface for agent strategies."""

    def setup(self, cfg=None, window_capture=None) -> None:
        """Initialise the strategy with configuration and window capture."""
        ...

    def step(self) -> None:
        """Execute a single step of the strategy."""
        ...


_STRATEGIES: Dict[str, Type[AgentStrategy]] = {}


def register(name: str) -> Callable[[Type[AgentStrategy]], Type[AgentStrategy]]:
    """Decorator registering a strategy implementation under ``name``."""

    def decorator(cls: Type[AgentStrategy]) -> Type[AgentStrategy]:
        _STRATEGIES[name] = cls
        return cls

    return decorator


def load_strategy(cfg=None, window_capture=None) -> AgentStrategy:
    """Load and instantiate strategy specified in ``cfg``.

    The configuration may contain the key ``"strategy"`` naming the desired
    strategy module.  Strategies register themselves via :func:`register`.
    """

    name = (cfg or {}).get("strategy", "hunt_destroy")
    if name not in _STRATEGIES:
        importlib.import_module(f"agent.{name}")
    cls = _STRATEGIES.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy '{name}'")
    strategy = cls()
    strategy.setup(cfg, window_capture)
    return strategy


__all__ = ["AgentStrategy", "register", "load_strategy"]
