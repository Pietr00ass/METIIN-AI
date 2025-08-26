from __future__ import annotations

import time
import os
import numpy as np
import pyautogui
import easyocr

from recorder.window_capture import WindowCapture
from .template_matcher import TemplateMatcher
from .wasd import KeyHold

pyautogui.PAUSE = 0.02


class Teleporter:
    """
    Panel teleportu:
    - open_panel(): Ctrl+X (z focusem)
    - go_page('Strona I'..'Strona VIII')
    - teleport(point, page)
    - teleport_slot(slot, page): scroll + retry, klik 'Wczytaj'
    Wymaga szablonów: wczytaj.png, strona_I.png..strona_VIII.png
    """

    def __init__(self, win: WindowCapture, templates_dir: str, use_ocr: bool = True, dry: bool = False):
        self.win = win
        if not os.path.isdir(templates_dir):
            raise FileNotFoundError(f"Brak katalogu z szablonami: {templates_dir}")
        required = ["wczytaj.png"] + [f"strona_{r}.png" for r in ["I","II","III","IV","V","VI","VII","VIII"]]
        missing = [p for p in required if not os.path.isfile(os.path.join(templates_dir, p))]
        if missing:
            raise FileNotFoundError(f"Brak plików w {templates_dir}: {', '.join(missing)}")
        self.tm = TemplateMatcher(templates_dir)
        self.reader = easyocr.Reader(["pl", "en"], gpu=False) if use_ocr else None
        self.dry = dry
        self.keys = KeyHold(dry=self.dry, active_fn=getattr(self.win, "is_foreground", None))

    def _frame(self) -> np.ndarray:
        fr = self.win.grab()
        return np.array(fr)[:, :, :3].copy()

    def _safe_click(self, x: int, y: int) -> None:
        if self.dry:
            return
        pyautogui.moveTo(x, y, duration=0.05)
        pyautogui.click()

    def open_panel(self) -> None:
        self.win.focus()
        if not self.dry:
            self.keys.press("ctrl")
            self.keys.press("x")
            time.sleep(0.05)
            self.keys.release("x")
            self.keys.release("ctrl")
            time.sleep(0.35)

    def go_page(self, page_label: str, thresh: float = 0.82) -> bool:
        token = page_label.split()[-1].upper().replace(" ", "_")
        name = f"strona_{token}"
        _, _, w, h = self.win.region
        roi = (int(w * 0.05), int(h * 0.82), int(w * 0.9), int(h * 0.16))
        frame = self._frame()
        m = self.tm.find(frame, name, thresh=thresh, roi=roi, multi_scale=True)
        if not m:
            return False
        L, T, _, _ = self.win.region
        cx, cy = m["center"]
        self._safe_click(L + cx, T + cy)
        time.sleep(0.25)
        return True

    def _find_row_by_text(self, target_text: str):
        frame = self._frame()
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.16):int(h * 0.70), int(w * 0.05):int(w * 0.55)]
        if self.reader is None:
            return None
        results = self.reader.readtext(roi)
        target_low = target_text.lower().strip()
        for bbox, text, _ in results:
            if text.lower().strip() == target_low:
                (x0, y0), (x1, y1) = bbox[0], bbox[2]
                return int((x0 + x1) // 2), int((y0 + y1) // 2)
        return None

    # ---- teleportacja ----
    def teleport_slot(self, slot: int, page_label: str) -> bool:
        """Teleportuj do danego numeru slotu na podanej stronie.

        Zwraca ``True`` gdy udało się kliknąć w przycisk ``Wczytaj`` dla
        wskazanego slotu. Metoda korzysta z prostego OCR do odszukania
        wiersza z numerem slotu.
        """

        # otwórz panel i przejdź do strony
        self.open_panel()
        if not self.go_page(page_label):
            return False

        # wyszukaj wiersz slotu (OCR)
        pos = self._find_row_by_text(str(slot))
        if pos is None:
            return False

        # przekształć współrzędne z ROI na współrzędne ekranu
        L, T, w, h = self.win.region
        roi_x = int(w * 0.05)
        roi_y = int(h * 0.16)
        abs_x = L + roi_x + pos[0]
        abs_y = T + roi_y + pos[1]
        self._safe_click(abs_x, abs_y)
        time.sleep(0.15)

        # przycisk "wczytaj"
        frame = self._frame()
        m = self.tm.find(frame, "wczytaj", thresh=0.8, multi_scale=True)
        if not m:
            return False
        cx, cy = m["center"]
        self._safe_click(L + cx, T + cy)
        time.sleep(0.35)
        return True

    def teleport(self, slot: int, page_label: str) -> bool:
        """Zachowana dla kompatybilności nazwa ``teleport``."""
        return self.teleport_slot(slot, page_label)

