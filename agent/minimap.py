from __future__ import annotations

from typing import List, Tuple
import numpy as np

from .game_controller import controller

# Global reference to the latest minimap grid used for path finding
_minimap: np.ndarray | None = None


def extract_player_pos(frame: np.ndarray) -> Tuple[int, int] | None:
    """Extract player position from a minimap ``frame``.

    The frame is expected to contain integer values where ``0`` denotes a
    walkable tile, ``1`` an obstacle and ``2`` marks the player's current
    location.  The function updates ``GameState.player_pos`` on the global
    controller if available and returns the detected position as ``(x, y)``.
    """

    global _minimap
    _minimap = np.array(frame, copy=True)
    loc = np.argwhere(_minimap == 2)
    if loc.size == 0:
        return None
    y, x = map(int, loc[0])
    pos = (x, y)
    if controller is not None and getattr(controller, "state", None) is not None:
        controller.state.player_pos = pos
    return pos


def navigate_to(target_xy: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Compute a path from current ``player_pos`` to ``target_xy``.

    A simple A* search is performed on the most recent minimap grid.  The
    function returns the list of coordinates from start to target (inclusive).
    If a path is found the player's position in :class:`GameState` is updated
    to the target coordinate.
    """

    if _minimap is None or controller is None or getattr(controller, "state", None) is None:
        return []
    start = controller.state.player_pos
    if start is None:
        return []
    goal = tuple(map(int, target_xy))
    height, width = _minimap.shape[:2]

    def neighbors(node: Tuple[int, int]):
        x, y = node
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and _minimap[ny, nx] != 1:
                yield (nx, ny)

    def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    import heapq

    open_set: list[tuple[int, int, Tuple[int, int]]] = []
    heapq.heappush(open_set, (heuristic(start, goal), 0, start))
    came_from: dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: dict[Tuple[int, int], int] = {start: 0}

    while open_set:
        _, cost, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            controller.state.player_pos = goal
            return path
        for nb in neighbors(current):
            tentative = cost + 1
            if tentative < g_score.get(nb, 1 << 30):
                came_from[nb] = current
                g_score[nb] = tentative
                f = tentative + heuristic(nb, goal)
                heapq.heappush(open_set, (f, tentative, nb))
    return []


__all__ = ["extract_player_pos", "navigate_to"]
