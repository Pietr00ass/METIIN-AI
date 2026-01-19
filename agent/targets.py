from __future__ import annotations

from utils.classes import TARGET_PRIORITY

from .detector import Detection

DEFAULT_PRIORITY = list(TARGET_PRIORITY)


def _rank(name: str, priority_order: list[str]) -> int:
    try:
        return len(priority_order) - priority_order.index(name)
    except ValueError:
        return 0


def pick_target(
    dets: list[Detection],
    wh: tuple[int, int],
    priority_order: list[str] | None = None,
    center_bias: float = 2.0,
    size_bias: float = 1.0,
    center_y: float = 0.55,
) -> Detection | None:
    if not dets:
        return None
    W, H = wh
    order = priority_order or DEFAULT_PRIORITY

    def score(d: Detection):
        x1, y1, x2, y2 = d.bbox
        cx = (x1 + x2) / 2 / W
        cy = (y1 + y2) / 2 / H
        bw = (x2 - x1) / W
        bh = (y2 - y1) / H
        pr = _rank(d.name, order)
        dist = abs(cx - 0.5) + abs(cy - center_y)
        return (
            pr * 10
            - center_bias * dist
            + size_bias * (bw * bh)
            + 0.2 * d.conf
        )

    dets = sorted(dets, key=score, reverse=True)
    return dets[0]
