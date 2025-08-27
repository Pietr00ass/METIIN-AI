from __future__ import annotations
import time
from .wasd import KeyHold


class AreaScanner:
    """Rotate the character to scan the surrounding area.

    Metin2 exposes a key that spins the camera around the character.  By
    repeatedly pressing and releasing this key we can simulate a player
    turning in place, giving the detector a chance to see targets hidden
    outside the initial field of view.
    """

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
        """Perform the scan by slowly rotating the camera.

        ``sweep_ms`` controls how long the spin key is held which translates
        roughly into the angle of rotation.  After ``sweeps`` iterations the
        character has usually completed a full 360° turn.
        """

        # Allow the game to settle before starting the rotation, otherwise
        # the first frames may still show the previous teleport location.
        time.sleep(self.idle_sec)
        for _ in range(self.sweeps):
            self.keys.press(self.spin_key)
            time.sleep(self.sweep_ms / 1000.0)
            self.keys.release(self.spin_key)
            # Small pause between sweeps ensures the key tap is registered and
            # gives the detector time to process the new view.
            time.sleep(self.pause)
