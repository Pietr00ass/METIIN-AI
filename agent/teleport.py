from __future__ import annotations

import logging
import os
import time
from enum import Enum, auto

import easyocr
import numpy as np
import pyautogui
from PIL import Image

from recorder.window_capture import WindowCapture

from . import get_config
from .template_matcher import TemplateMatcher
from .wasd import KeyHold

CFG = get_config()
pyautogui.PAUSE = CFG.get("controls", {}).get("mouse_pause", 0.02)

logger = logging.getLogger(__name__)


class TeleportResult(Enum):
    OK = "ok"
    TEMPLATE_NOT_FOUND = "template_not_found"
    OCR_MISS = "ocr_miss"
    WINDOW_NOT_FOREGROUND = "window_not_foreground"


class Teleporter:
    """
    Panel teleportu:
    - open_panel(): Ctrl+X (z focusem)
    - go_page('Strona I'..'Strona VIII')
    - teleport(point, page)
    - teleport_slot(slot, page): scroll + retry, klik 'Wczytaj'
    Wymaga szablonów: wczytaj.png, strona_I.png..strona_VIII.png
    """

    def __init__(
        self,
        win: WindowCapture,
        templates_dir: str,
        use_ocr: bool = True,
        dry: bool = False,
        cfg: dict | None = None,
    ):
        self.cfg = cfg or CFG
        self.win = win
        if not os.path.isdir(templates_dir):
            raise FileNotFoundError(f"Brak katalogu z szablonami: {templates_dir}")
        required = ["wczytaj.png"] + [
            f"strona_{r}.png"
            for r in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        ]
        missing = [
            p for p in required if not os.path.isfile(os.path.join(templates_dir, p))
        ]
        if missing:
            raise FileNotFoundError(
                f"Brak plików w {templates_dir}: {', '.join(missing)}"
            )
        self.tm = TemplateMatcher(templates_dir)
        self.reader = easyocr.Reader(["pl", "en"], gpu=False) if use_ocr else None
        self.dry = dry
        self.keys = KeyHold(
            dry=self.dry, active_fn=getattr(self.win, "is_foreground", None)
        )
        tp_cfg = self.cfg.get("teleport", {})
        self.click_duration = tp_cfg.get("click_duration", 0.05)
        self.open_panel_delay = tp_cfg.get("open_panel_delay", 0.35)
        self.page_thresh = tp_cfg.get("page_thresh", 0.82)
        self.after_page_delay = tp_cfg.get("after_page_delay", 0.25)
        self.row_click_delay = tp_cfg.get("row_click_delay", 0.15)
        self.load_btn_thresh = tp_cfg.get("load_btn_thresh", 0.8)
        self.after_load_delay = tp_cfg.get("after_load_delay", 0.35)

    def _frame(self) -> np.ndarray:
        fr = self.win.grab()
        return np.array(fr)[:, :, :3].copy()

    def _save_panel(self, frame: np.ndarray, reason: TeleportResult) -> None:
        """Save current panel frame for debugging failures."""
        try:
            log_dir = self.cfg.get("paths", {}).get("log_dir", "runs")
            os.makedirs(log_dir, exist_ok=True)
            fname = os.path.join(
                log_dir, f"tp_fail_{reason.value}_{int(time.time())}.png"
            )
            Image.fromarray(frame).save(fname)
            logger.debug("Teleport failure screenshot saved to %s", fname)
        except Exception:
            logger.debug("Could not save teleport failure screenshot", exc_info=True)

    def _safe_click(self, x: int, y: int) -> None:
        if self.dry:
            return
        if not self.win.is_foreground():
            self.win.focus()
            if not self.win.is_foreground():
                return
        pyautogui.moveTo(x, y, duration=self.click_duration)
        pyautogui.click()

    def open_panel(self, max_attempts: int = 3, ref_name: str = "strona_I") -> bool:
        """Open teleport panel and verify it appears.

        Sends the ``Ctrl+X`` hotkey, takes a screenshot and checks whether a
        reference template is visible.  The check is performed first with
        :class:`TemplateMatcher` and then, if needed, with
        :func:`pyautogui.locateOnScreen`.  When the panel is not detected the
        hotkey is retried ``max_attempts`` times before raising
        :class:`RuntimeError`.
        """

        if not self.win.is_foreground():
            self.win.focus()
            if not self.win.is_foreground():
                return False

        L, T, w, h = self.win.region
        roi = (
            L + int(w * 0.05),
            T + int(h * 0.82),
            int(w * 0.9),
            int(h * 0.16),
        )
        template_path = self.tm.dir / f"{ref_name}.png"

        for attempt in range(max_attempts):
            if not self.dry:
                pyautogui.hotkey("ctrl", "x")
            time.sleep(self.open_panel_delay)

            screenshot = pyautogui.screenshot()
            frame = np.array(screenshot)[:, :, ::-1]

            found = self.tm.find(
                frame,
                ref_name,
                thresh=self.page_thresh,
                roi=roi,
                multi_scale=True,
            )

            if not found:
                try:
                    found = pyautogui.locateOnScreen(
                        str(template_path),
                        region=roi,
                        confidence=self.page_thresh,
                    )
                except Exception:
                    found = None

        if found:
            return True

        raise RuntimeError("Teleport panel not detected")

    def close_panel(self) -> None:
        """Close the teleport panel if it is open."""
        if self.dry:
            return
        pyautogui.press("esc")

    def go_page(self, page_label: str, thresh: float | None = None) -> bool:
        token = page_label.split()[-1].upper().replace(" ", "_")
        name = f"strona_{token}"
        _, _, w, h = self.win.region
        roi = (int(w * 0.05), int(h * 0.82), int(w * 0.9), int(h * 0.16))
        frame = self._frame()
        m = self.tm.find(
            frame, name, thresh=thresh or self.page_thresh, roi=roi, multi_scale=True
        )
        if not m:
            return False
        L, T, _, _ = self.win.region
        cx, cy = m["center"]
        self._safe_click(L + cx, T + cy)
        time.sleep(self.after_page_delay)
        return True

    def _find_row_by_text(self, target_text: str):
        frame = self._frame()
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.16) : int(h * 0.70), int(w * 0.05) : int(w * 0.55)]
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
    def teleport_slot(self, slot: int, page_label: str) -> TeleportResult:
        """Teleportuj do danego numeru slotu na podanej stronie.

        Zwraca :class:`TeleportResult` opisujący rezultat próby
        teleportacji.  Przy niepowodzeniu zrzut panelu jest zapisywany w
        ``runs/`` (lub w katalogu wskazanym przez ``paths.log_dir`` w
        konfiguracji).
        """

        # otwórz panel i przejdź do strony
        self.open_panel()
        if not self.win.is_foreground():
            return TeleportResult.WINDOW_NOT_FOREGROUND
        if not self.go_page(page_label):
            frame = self._frame()
            self._save_panel(frame, TeleportResult.TEMPLATE_NOT_FOUND)
            return TeleportResult.TEMPLATE_NOT_FOUND

        # wyszukaj wiersz slotu (OCR)
        pos = self._find_row_by_text(str(slot))
        if pos is None:
            frame = self._frame()
            self._save_panel(frame, TeleportResult.OCR_MISS)
            return TeleportResult.OCR_MISS

        # przekształć współrzędne z ROI na współrzędne ekranu
        L, T, w, h = self.win.region
        roi_x = int(w * 0.05)
        roi_y = int(h * 0.16)
        abs_x = L + roi_x + pos[0]
        abs_y = T + roi_y + pos[1]
        self._safe_click(abs_x, abs_y)
        time.sleep(self.row_click_delay)

        # przycisk "wczytaj"
        frame = self._frame()
        m = self.tm.find(
            frame, "wczytaj", thresh=self.load_btn_thresh, multi_scale=True
        )
        if not m:
            self._save_panel(frame, TeleportResult.TEMPLATE_NOT_FOUND)
            return TeleportResult.TEMPLATE_NOT_FOUND
        cx, cy = m["center"]
        self._safe_click(L + cx, T + cy)
        time.sleep(self.after_load_delay)
        return TeleportResult.OK

    def teleport(self, slot: int, page_label: str) -> TeleportResult:
        """Zachowana dla kompatybilności nazwa ``teleport``."""
        return self.teleport_slot(slot, page_label)
