from __future__ import annotations

import time
import random

import pyautogui
import numpy as np

try:  # avoid circular import during tests
    from recorder.window_capture import WindowCapture
except Exception:  # pragma: no cover - optional dependency in tests
    WindowCapture = None

from . import get_config
from utils.humanizer import maybe_micro_pause, maybe_mistake_offset
from utils.mouse_paths import generate_bezier_path, move_along_path, path_as_int

_LAST_CLICK_TS = 0.0
_MAX_CPS = 5  # klików na sekundę (limit bezpieczeństwa)


def _rate_limit_ok() -> bool:
    global _LAST_CLICK_TS
    now = time.time()
    min_dt = 1.0 / _MAX_CPS
    if now - _LAST_CLICK_TS >= min_dt:
        _LAST_CLICK_TS = now
        return True
    return False


def click_bbox_center(
    bbox,
    region,
    rate_limit: bool = True,
    win: WindowCapture | None = None,
    button: str = "left",
) -> bool:
    """Click the centre of ``bbox`` within ``region`` if the window is active.

    Parameters
    ----------
    bbox, region: tuple
        Target and region coordinates.
    rate_limit: bool
        Whether to limit the number of clicks per second.
    win: WindowCapture | None
        Optional window instance used to verify focus.
    button: str
        Mouse button to use (e.g. ``"left"`` or ``"right"``).

    Returns
    -------
    bool
        ``True`` if the click was performed.

    PL: Kliknij w środek ``bbox`` w obrębie ``region`` jeśli okno jest aktywne.
    """

    x1, y1, x2, y2 = bbox
    left, top, width, height = region
    cx = int(left + (x1 + x2) / 2)
    cy = int(top + (y1 + y2) / 2)

    if win is not None:
        win.focus()
        if not win.is_foreground():
            return False

    if not rate_limit or _rate_limit_ok():
        cfg = get_config()
        humanizer = cfg.humanizer
        dx, dy = maybe_mistake_offset(
            humanizer.click_miss_chance,
            humanizer.click_miss_offset,
        )
        cx = int(cx + dx)
        cy = int(cy + dy)
        if (
            humanizer.mouse_path_chance > 0
            and random.random() < humanizer.mouse_path_chance
        ):
            pos_fn = getattr(pyautogui, "position", None)
            start = None
            if callable(pos_fn):
                try:
                    start = pos_fn()
                except Exception:
                    start = None
            if start is not None:
                path = generate_bezier_path(
                    (start[0], start[1]),
                    (cx, cy),
                    steps=humanizer.mouse_path_steps,
                    spread=humanizer.mouse_path_spread,
                )
                move_along_path(pyautogui.moveTo, path_as_int(path), duration=0)
            else:
                pyautogui.moveTo(cx, cy, duration=0)
        else:
            pyautogui.moveTo(cx, cy, duration=0)
        maybe_micro_pause()
        pyautogui.click(button=button)
        return True
    return False


def burst_click(
    bbox,
    region,
    n: int = 3,
    interval: float = 0.08,
    win: WindowCapture | None = None,
    button: str = "left",
):
    """Series of clicks within ``bbox`` while ensuring window focus.

    Parameters
    ----------
    bbox, region: tuple
        Target and region coordinates.
    n: int
        Number of clicks to perform.
    interval: float
        Delay between clicks in seconds.
    win: WindowCapture | None
        Optional window instance for focus verification.
    button: str
        Mouse button used for the clicks.

    PL: Seria kliknięć w ``bbox`` z zachowaniem bezpieczeństwa fokusu.
    """
    for _ in range(n):
        if not click_bbox_center(bbox, region, rate_limit=False, win=win, button=button):
            break
        time.sleep(interval)


def right_click_bbox_center(
    bbox,
    region,
    rate_limit: bool = True,
    win: WindowCapture | None = None,
) -> bool:
    """Convenience wrapper performing a right click on ``bbox`` centre.

    Parameters mirror :func:`click_bbox_center` but always use the right mouse
    button.  Returns ``True`` when the click was executed.
    """

    return click_bbox_center(
        bbox,
        region,
        rate_limit=rate_limit,
        win=win,
        button="right",
    )


def detect_and_right_click(
    detector,
    region,
    *,
    frame=None,
    target_names: list[str] | None = None,
    win: WindowCapture | None = None,
    rate_limit: bool = True,
    click_all: bool = False,
) -> bool:
    """Detect objects and right-click matching ones.

    The frame to analyse can be provided explicitly via ``frame``.  If omitted
    the function grabs the current window contents using ``win``.  Detection
    results are iterated in the order returned by ``detector.infer`` and each
    matching object is right-clicked.  Set ``click_all`` to ``True`` to interact
    with all matches instead of stopping after the first click.

    Parameters
    ----------
    detector:
        Object with ``infer(frame)`` -> list of detections exposing ``name`` and
        ``bbox``.
    region: tuple
        ``(left, top, width, height)`` used to translate detection coordinates to
        screen space.
    frame: np.ndarray or ``None``
        Optional BGR image; if ``None`` and ``win`` is provided the image will be
        captured from the window.
    target_names: list[str] or ``None``
        Detection names to click.  ``None`` matches all objects.
    win: WindowCapture | None
        Optional window instance for capture and focus verification.
    rate_limit: bool
        Forwarded to :func:`click_bbox_center`.
    click_all: bool
        Whether to click all matching detections.

    Returns
    -------
    bool
        ``True`` if at least one click was performed.

    PL: Wykryj obiekty na klatce i kliknij prawym przyciskiem wszystkie pasujące
    do ``target_names`` (domyślnie pierwszy znaleziony obiekt).
    """

    if frame is None:
        if win is None:
            raise ValueError("frame or win must be provided")
        fr = win.grab()
        frame = np.array(fr)[:, :, :3].copy()

    dets = detector.infer(frame)
    clicked = False
    for d in dets:
        if target_names is None or d.name in target_names:
            ok = click_bbox_center(
                d.bbox,
                region,
                rate_limit=rate_limit,
                win=win,
                button="right",
            )
            clicked = clicked or ok
            if ok and not click_all:
                break
    return clicked
