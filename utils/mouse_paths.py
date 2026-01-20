from __future__ import annotations

import math
import random
import time
from typing import Callable, Iterable, Sequence


Point = tuple[float, float]


def _control_points(start: Point, end: Point, spread: float) -> tuple[Point, Point]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    distance = math.hypot(dx, dy) or 1.0
    spread_px = spread if spread >= 1.0 else distance * spread
    perp_x, perp_y = -dy / distance, dx / distance
    c1_scale = random.uniform(0.2, 0.4)
    c2_scale = random.uniform(0.6, 0.8)
    c1_offset = random.uniform(-spread_px, spread_px)
    c2_offset = random.uniform(-spread_px, spread_px)
    c1 = (
        start[0] + dx * c1_scale + perp_x * c1_offset,
        start[1] + dy * c1_scale + perp_y * c1_offset,
    )
    c2 = (
        start[0] + dx * c2_scale + perp_x * c2_offset,
        start[1] + dy * c2_scale + perp_y * c2_offset,
    )
    return c1, c2


def bezier_point(start: Point, c1: Point, c2: Point, end: Point, t: float) -> Point:
    """Return a point on the cubic Bezier curve at ``t`` in [0, 1]."""
    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t
    x = uuu * start[0]
    x += 3 * uu * t * c1[0]
    x += 3 * u * tt * c2[0]
    x += ttt * end[0]
    y = uuu * start[1]
    y += 3 * uu * t * c1[1]
    y += 3 * u * tt * c2[1]
    y += ttt * end[1]
    return x, y


def generate_bezier_path(
    start: Point, end: Point, *, steps: int = 20, spread: float = 12.0
) -> list[Point]:
    """Generate a list of points approximating a Bezier curve."""
    if steps < 2:
        steps = 2
    c1, c2 = _control_points(start, end, spread)
    return [bezier_point(start, c1, c2, end, i / (steps - 1)) for i in range(steps)]


def bezier_point_between(
    start: Point, end: Point, *, progress: float, spread: float = 12.0
) -> Point:
    """Return a single point at ``progress`` along a randomized Bezier curve."""
    progress = max(0.0, min(1.0, progress))
    c1, c2 = _control_points(start, end, spread)
    return bezier_point(start, c1, c2, end, progress)


def move_along_path(
    move_fn: Callable[..., None],
    points: Sequence[Point],
    *,
    duration: float = 0.0,
) -> None:
    """Move the cursor through ``points`` using ``move_fn``."""
    if not points:
        return
    step_delay = 0.0
    if duration and len(points) > 1:
        step_delay = max(duration / (len(points) - 1), 0.0)
    for idx, (x, y) in enumerate(points):
        move_fn(x, y, duration=0)
        if step_delay and idx < len(points) - 1:
            time.sleep(step_delay)


def path_as_int(points: Iterable[Point]) -> list[tuple[int, int]]:
    """Convert float points into integer pixel coordinates."""
    return [(int(round(x)), int(round(y))) for x, y in points]

