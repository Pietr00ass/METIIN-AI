from __future__ import annotations

import cv2


class TemplateMatcher:
    def __init__(self, templates: dict):
        self.templates = {k: v for k, v in templates.items() if v is not None}

    def find(self, frame_bgr, key: str, thr=0.82):
        tpl = self.templates.get(key)
        if tpl is None:
            return None, 0.0
        res = cv2.matchTemplate(frame_bgr, tpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < thr:
            return None, max_val
        h, w = tpl.shape[:2]
        x1, y1 = max_loc
        return (x1, y1, x1 + w, y1 + h), max_val
