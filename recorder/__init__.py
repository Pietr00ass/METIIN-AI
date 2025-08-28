"""Recorder package providing screen capture utilities."""

import importlib
from types import ModuleType

__all__ = ["capture", "align_wasd"]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
