from __future__ import annotations

import time

import pyautogui

try:  # avoid circular import during tests
    from recorder.window_capture import WindowCapture
except Exception:  # pragma: no cover - optional dependency in tests
    WindowCapture = None

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
        pyautogui.moveTo(cx, cy, duration=0)
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
    frame,
    region,
    target_names: list[str] | None = None,
    win: WindowCapture | None = None,
    rate_limit: bool = True,
) -> bool:
    """Detect objects on ``frame`` and right‑click the first match.

    Parameters
    ----------
    detector:
        Object providing ``infer(frame)`` -> list of detections with ``name`` and
        ``bbox`` attributes.
    frame: np.ndarray
        BGR image captured from the application window.
    region: tuple
        ``(left, top, width, height)`` describing window position used for
        translating detection coordinates to screen space.
    target_names: list[str] or None
        Optional list of detection names to look for.  If ``None`` the first
        detected object is clicked.
    win: WindowCapture | None
        Optional window instance for focus verification.

    Returns
    -------
    bool
        ``True`` if a right click was performed on a detected object.

    PL: Wykryj obiekty na klatce i kliknij prawym przyciskiem pierwszy pasujący
    do ``target_names``.
    """

    dets = detector.infer(frame)
    for d in dets:
        if target_names is None or d.name in target_names:
            return click_bbox_center(
                d.bbox,
                region,
                rate_limit=rate_limit,
                win=win,
                button="right",
            )
    return False
