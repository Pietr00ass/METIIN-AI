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

def click_bbox_center(bbox, region, rate_limit: bool = True, win: WindowCapture | None = None) -> bool:
    """Kliknij w środek ``bbox`` w obrębie ``region`` jeśli okno jest aktywne.

    Parameters
    ----------
    bbox, region: tuple
        Współrzędne celu i obszaru w jakim się znajduje.
    rate_limit: bool
        Czy stosować ograniczenie liczby klików na sekundę.
    win: WindowCapture | None
        Opcjonalna instancja okna pozwalająca sprawdzić fokus.

    Returns
    -------
    bool
        ``True`` jeśli kliknięcie zostało wykonane.
    """

    x1, y1, x2, y2 = bbox
    left, top, width, height = region
    cx = int(left + (x1 + x2) / 2)
    cy = int(top + (y1 + y2) / 2)

    if win is not None:
        if not win.is_foreground():
            win.focus()
            if not win.is_foreground():
                return False

    if not rate_limit or _rate_limit_ok():
        pyautogui.moveTo(cx, cy, duration=0)
        pyautogui.click()
        return True
    return False


def burst_click(bbox, region, n=3, interval=0.08, win: WindowCapture | None = None):
    """Seria kliknięć w ``bbox`` z zachowaniem bezpieczeństwa fokusu."""
    for _ in range(n):
        if not click_bbox_center(bbox, region, rate_limit=False, win=win):
            break
        time.sleep(interval)
