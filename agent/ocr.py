from __future__ import annotations

import easyocr


class Ocr:
    """Wrapper around EasyOCR with a safer language initialisation.

    EasyOCR requires that model files for requested languages are present on
    disk.  When a language pack has not been downloaded the library raises an
    exception which previously bubbled up to the caller.  This resulted in
    confusing errors such as "The localization resource could not be found".

    To make the behaviour more robust we now fall back to English when the
    desired language data is missing.
    """

    def __init__(self, lang: list[str] | None = None):
        if lang is None:
            lang = ["pl", "en"]
        try:
            self.reader = easyocr.Reader(lang, gpu=False)
        except Exception:  # pragma: no cover - defensive fallback
            # Fallback to English if the requested localization resources are
            # not available on the system.
            self.reader = easyocr.Reader(["en"], gpu=False)

    def find_label(self, frame_bgr, query: str):
        res = self.reader.readtext(frame_bgr)
        best = None
        best_c = 0
        for box, text, conf in res:
            if query.lower() in text.lower() and conf > best_c:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                best = (x1, y1, x2, y2)
                best_c = conf
        return best, best_c
