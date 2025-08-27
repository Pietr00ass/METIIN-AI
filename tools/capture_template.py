"""Capture a GUI template from the Metin2 window.

This helper script grabs a region of the Metin2 game window and saves it as
an image template.  GUI operations such as locating the window and capturing a
frame are wrapped in ``try``/``except`` blocks to avoid crashing when the
window is missing or inaccessible.  Logging is used instead of ``print`` so
messages can easily be filtered or redirected.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

from recorder.window_capture import WindowCapture

logging.basicConfig(level=logging.INFO)


def main() -> None:
    out = Path("assets/templates")
    out.mkdir(parents=True, exist_ok=True)

    try:
        wc = WindowCapture("Metin2")  # fragment tytułu
        if not wc.locate(timeout=5):
            raise RuntimeError("Nie znaleziono okna")
        frame = np.array(wc.grab())[:, :, :3]

        # ustaw ROI ręcznie na start
        x, y, w, h = 1000, 80, 90, 30
        name = "wczytaj"
        out_path = out / f"{name}.png"
        cv2.imwrite(str(out_path), frame[y : y + h, x : x + w])
        logging.info("Zapisano szablon: %s", out_path)
    except Exception as exc:
        logging.error("Błąd podczas przechwytywania szablonu: %s", exc)


if __name__ == "__main__":
    main()
