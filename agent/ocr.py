from __future__ import annotations
import easyocr

class Ocr:
    def __init__(self, lang=['pl', 'en']):
        self.reader = easyocr.Reader(lang, gpu=False)

    def find_label(self, frame_bgr, query: str):
        res = self.reader.readtext(frame_bgr)
        best = None; best_c = 0
        for (box, text, conf) in res:
            if query.lower() in text.lower() and conf > best_c:
                xs = [p[0] for p in box]; ys = [p[1] for p in box]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                best = (x1, y1, x2, y2); best_c = conf
        return best, best_c
