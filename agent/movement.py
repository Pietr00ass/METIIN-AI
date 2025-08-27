from __future__ import annotations

import logging

from .wasd import KeyHold

logger = logging.getLogger(__name__)


class MovementController:
    """Handle movement keys based on target position and obstacle steering."""

    def __init__(self, keys: KeyHold, desired_w: float, deadzone: float):
        self.keys = keys
        self.desired_w = desired_w
        self.deadzone = deadzone

    def move(self, tgt: dict | None, steer: str | None, frame_size: tuple[int, int]):
        """Update pressed keys to move towards the target and avoid obstacles.

        Parameters
        ----------
        tgt: dict or None
            Target detection dictionary with ``bbox``.
        steer: str or None
            Direction suggested by the obstacle avoidance system (``"left"`` or
            ``"right"``).
        frame_size: tuple[int, int]
            Width and height of the current frame.

        Returns
        -------
        float | None
            Normalised target width (``bbox`` width divided by frame width) or
            ``None`` when no target is provided.
        """
        W, H = frame_size
        desired: set[str] = set()

        if steer == "left":
            logger.debug("Omijanie przeszkody: skręt w lewo")
            desired.add("a")
        elif steer == "right":
            logger.debug("Omijanie przeszkody: skręt w prawo")
            desired.add("d")

        bw = None
        if tgt:
            x1, y1, x2, y2 = tgt["bbox"]
            cx = (x1 + x2) / 2 / W
            bw = (x2 - x1) / W
            if abs(cx - 0.5) > self.deadzone:
                desired.add("d" if cx > 0.5 else "a")
            if bw < self.desired_w * 0.95:
                desired.add("w")
            elif bw > self.desired_w * 1.25:
                desired.add("s")

        for k in self.keys.down - desired:
            self.keys.release(k)
        for k in desired - self.keys.down:
            self.keys.press(k)

        return bw
