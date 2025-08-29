from __future__ import annotations

from math import hypot
from pathlib import Path

import cv2
import numpy as np


class TemplateMatcher:
    def __init__(
        self,
        templates_dir: str = "assets/templates",
        method: int = cv2.TM_CCOEFF_NORMED,
    ):
        self.dir = Path(templates_dir)
        self.method = method
        self.cache = {}

    def load(self, name: str):
        if name in self.cache:
            return self.cache[name]
        p = self.dir / f"{name}.png"
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Brak szablonu: {p}")
        img = cv2.GaussianBlur(img, (3, 3), 0)
        self.cache[name] = img
        return img

    def _prep(self, frame_bgr, roi):
        if roi is not None:
            x, y, w, h = roi
            crop = frame_bgr[y : y + h, x : x + w]
            if crop.size == 0:
                raise ValueError(f"Invalid ROI {roi}: empty crop")
        else:
            x = y = 0
            h, w = frame_bgr.shape[:2]
            crop = frame_bgr
            if crop.size == 0:
                raise ValueError("Empty frame for template matching")
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return gray, x, y

    def find(
        self,
        frame_bgr: np.ndarray,
        name: str,
        thresh=0.82,
        roi=None,
        multi_scale=False,
        scales=(1.0, 0.9, 1.1),
    ):
        gray, offx, offy = self._prep(frame_bgr, roi)
        tpl0 = self.load(name)
        best = None
        for s in [1.0] if not multi_scale else scales:
            tpl = cv2.resize(
                tpl0,
                (max(1, int(tpl0.shape[1] * s)), max(1, int(tpl0.shape[0] * s))),
                interpolation=cv2.INTER_AREA,
            )
            if tpl.shape[0] >= gray.shape[0] or tpl.shape[1] >= gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, tpl, self.method)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= thresh:
                x, y = max_loc
                bw, bh = tpl.shape[1], tpl.shape[0]
                cand = {
                    "rect": (offx + x, offy + y, bw, bh),
                    "center": (offx + x + bw // 2, offy + y + bh // 2),
                    "score": float(max_val),
                }
                if best is None or cand["score"] > best["score"]:
                    best = cand
        return best

    def find_all(
        self,
        frame_bgr: np.ndarray,
        name: str,
        thresh=0.82,
        roi=None,
        multi_scale=True,
        scales=(1.0, 0.9, 1.1, 0.8),
        dedup_px=12,
    ):
        """Zwraca listę dopasowań (słowniki) posortowanych po Y (od góry)."""
        gray, offx, offy = self._prep(frame_bgr, roi)
        tpl0 = self.load(name)
        found = []
        for s in [1.0] if not multi_scale else scales:
            tpl = cv2.resize(
                tpl0,
                (max(1, int(tpl0.shape[1] * s)), max(1, int(tpl0.shape[0] * s))),
                interpolation=cv2.INTER_AREA,
            )
            if tpl.shape[0] >= gray.shape[0] or tpl.shape[1] >= gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, tpl, self.method)
            ys, xs = np.where(res >= thresh)
            for y, x in zip(ys, xs):
                bw, bh = tpl.shape[1], tpl.shape[0]
                cx, cy = offx + x + bw // 2, offy + y + bh // 2
                score = float(res[y, x])
                dup = False
                for f in found:
                    if hypot(f["center"][0] - cx, f["center"][1] - cy) < dedup_px:
                        if score > f["score"]:
                            f.update(
                                {
                                    "rect": (offx + x, offy + y, bw, bh),
                                    "center": (cx, cy),
                                    "score": score,
                                }
                            )
                        dup = True
                        break
                if not dup:
                    found.append(
                        {
                            "rect": (offx + x, offy + y, bw, bh),
                            "center": (cx, cy),
                            "score": score,
                        }
                    )
        found.sort(key=lambda d: d["center"][1])
        return found
