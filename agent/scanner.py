from __future__ import annotations
import time
from .wasd import KeyHold


class AreaScanner:
    """Rotate the character to scan the surrounding area."""

    def __init__(
        self,
        keys: KeyHold,
        spin_key: str = "e",
        sweep_ms: int = 250,
        sweeps: int = 8,
        idle_sec: float = 1.5,
        pause: float = 0.12,
    ):
        self.keys = keys
        self.spin_key = spin_key
        self.sweep_ms = sweep_ms
        self.sweeps = sweeps
        self.idle_sec = idle_sec
        self.pause = pause

    def scan(self) -> None:
        """Perform a scanning sweep by holding ``spin_key`` multiple times."""
        time.sleep(self.idle_sec)
        for _ in range(self.sweeps):
            self.keys.press(self.spin_key)
            time.sleep(self.sweep_ms / 1000.0)
            self.keys.release(self.spin_key)
            time.sleep(self.pause)
