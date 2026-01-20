from __future__ import annotations

from .wasd import KeyHold
from .game_controller import GameController
from .detector import Detection
from utils.logging_config import logger
import random

from utils.humanizer import jitter_move
from utils.mouse_paths import bezier_point_between
from . import get_config


class MovementController:
    """Handle movement keys based on target position and obstacle steering."""

    def __init__(
        self,
        controller: GameController | KeyHold,
        desired_w: float,
        deadzone: float,
        enabled: bool = True,
    ):
        if isinstance(controller, GameController):
            self.keys = controller.keys
        else:
            self.keys = controller
        self.desired_w = desired_w
        self.deadzone = deadzone
        self.enabled = enabled

    def move(
        self, tgt: Detection | None, steer: str | None, frame_size: tuple[int, int]
    ):
        """Update pressed keys to move towards the target and avoid obstacles.

        Parameters
        ----------
        tgt: Detection or None
            Target detection with ``bbox``.
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

        bw = None
        if not self.enabled:
            if tgt:
                x1, _, x2, _ = tgt.bbox
                bw = (x2 - x1) / W
            self.keys.release_all()
            return bw

        if steer == "left":
            logger.debug("Omijanie przeszkody: skręt w lewo")
            desired.add("a")
        elif steer == "right":
            logger.debug("Omijanie przeszkody: skręt w prawo")
            desired.add("d")

        bw = None
        if tgt:
            x1, y1, x2, y2 = tgt.bbox
            cx_px = (x1 + x2) / 2
            cy_px = (y1 + y2) / 2
            humanizer = get_config().humanizer
            jitter = humanizer.cursor_jitter
            jittered_x, jittered_y = jitter_move(cx_px, cy_px, jitter)
            if (
                humanizer.mouse_path_chance > 0
                and random.random() < humanizer.mouse_path_chance
            ):
                progress_min = max(0.0, humanizer.mouse_path_progress_min)
                progress_max = min(1.0, humanizer.mouse_path_progress_max)
                if progress_max < progress_min:
                    progress_max = progress_min
                progress = random.uniform(progress_min, progress_max)
                cx_px, cy_px = bezier_point_between(
                    (cx_px, cy_px),
                    (jittered_x, jittered_y),
                    progress=progress,
                    spread=humanizer.mouse_path_spread,
                )
            else:
                cx_px, cy_px = jittered_x, jittered_y
            cx = cx_px / W
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
