from __future__ import annotations
import time
import pyautogui

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

def click_bbox_center(bbox, region):
    x1, y1, x2, y2 = bbox
    left, top, width, height = region
    cx = int(left + (x1 + x2) / 2)
    cy = int(top + (y1 + y2) / 2)
    if _rate_limit_ok():
        pyautogui.moveTo(cx, cy, duration=0)
        pyautogui.click()

def burst_click(bbox, region, n=3, interval=0.08):
    for _ in range(n):
        click_bbox_center(bbox, region)
        time.sleep(interval)
