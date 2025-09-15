from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Iterable, List


class KeyProvider:
    """Protocol-like class for objects that can tap keys."""

    def tap(self, key: str) -> None:  # pragma: no cover - interface definition
        raise NotImplementedError


@dataclass
class Buff:
    """Single buff configuration and timer."""

    key: str
    interval_sec: float
    is_active: Callable[[], bool] | None = None
    next_time: float = field(default_factory=lambda: time.monotonic())

    def step(self, keys: KeyProvider) -> bool:
        """Check and cast buff if needed.

        Returns ``True`` if the key was pressed.
        """

        active = self.is_active() if self.is_active else False
        if active:
            return False
        now = time.monotonic()
        if now >= self.next_time:
            keys.tap(self.key)
            self.next_time = now + self.interval_sec
            return True
        return False


class BuffManager:
    """Manage multiple timed buffs."""

    def __init__(self, keys: KeyProvider, buffs: Iterable[Buff] | None = None):
        self.keys = keys
        self.buffs: List[Buff] = list(buffs or [])

    @classmethod
    def from_config(cls, cfg, keys: KeyProvider) -> "BuffManager":
        buffs = [Buff(b.key, b.interval_sec) for b in getattr(cfg, "buffs", [])]
        return cls(keys, buffs)

    def step(self) -> None:
        for buff in self.buffs:
            buff.step(self.keys)
