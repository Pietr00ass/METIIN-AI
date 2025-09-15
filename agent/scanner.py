from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable, Optional

from .wasd import KeyHold
from .game_controller import controller


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

        # internal state for asynchronous operation
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._completed = False
        self._progress = 0
        self._progress_cb: Optional[Callable[[float], None]] = None

    # ------------------------------------------------------------------
    # threading helpers
    def _run(self) -> None:
        """Worker method executed in a background thread."""

        # Allow the game to settle before starting the rotation
        time.sleep(self.idle_sec)
        for i in range(self.sweeps):
            if self._stop.is_set():
                break
            if controller is not None:
                move = controller.move_camera_left
                if self.spin_key.lower() not in {"q", "left"}:
                    move = controller.move_camera_right
                move(self.sweep_ms / 1000.0)
            else:
                self.keys.press(self.spin_key)
                if self._stop.wait(self.sweep_ms / 1000.0):
                    self.keys.release(self.spin_key)
                    break
                self.keys.release(self.spin_key)
            self._progress = (i + 1) / float(self.sweeps)
            if self._progress_cb:
                try:
                    self._progress_cb(self._progress)
                except Exception:
                    pass
            if self._stop.wait(self.pause):
                break
        else:
            # loop did not break -> full scan completed
            self._completed = True
        if controller is not None:
            controller.calibrate_camera()

    def scan(self, progress_cb: Optional[Callable[[float], None]] = None) -> None:
        """Start an asynchronous scan.

        Parameters
        ----------
        progress_cb: callable or None
            Callback invoked with a float in the ``0..1`` range each time a
            sweep is completed.
        """

        if self.is_scanning():
            return
        self._progress_cb = progress_cb
        self._progress = 0
        self._completed = False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    async def scan_async(
        self, progress_cb: Optional[Callable[[float], None]] = None
    ) -> None:
        """Asynchronous scan using ``asyncio`` for cooperative waits."""

        if self.is_scanning():
            return
        self.scan(progress_cb)
        while self.is_scanning():
            await asyncio.sleep(self.pause)

    def cancel(self) -> None:
        """Cancel the running scan if any."""

        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def is_scanning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def progress(self) -> float:
        return self._progress

    def is_done(self) -> bool:
        return self._completed and not self.is_scanning()

    def reset(self) -> None:
        """Reset completion flag so a new scan can begin."""

        self._completed = False
        self._progress = 0
