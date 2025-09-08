"""Capture a GUI template from the Metin2 window.

This helper script grabs a region of the Metin2 game window and saves it as
an image template.  GUI operations such as locating the window and capturing a
frame are wrapped in ``try``/``except`` blocks to avoid crashing when the
window is missing or inaccessible.  Logging is used instead of ``print`` so
messages can easily be filtered or redirected.

Usage
-----
``python tools/capture_template.py --roi X Y W H --name LABEL``

The ``--roi`` argument specifies the region of interest in pixels relative to
the Metin2 window, while ``--name`` determines the output filename.
"""

import argparse
import logging
from pathlib import Path

import cv2
import numpy as np

from recorder.window_capture import WindowCapture

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roi",
        nargs=4,
        type=int,
        metavar=("X", "Y", "W", "H"),
        default=[1000, 80, 90, 30],
        help="coordinates of the Metin2 window region (współrzędne regionu okna Metin2)",
    )
    parser.add_argument(
        "--name",
        default="wczytaj",
        help="output file name (nazwa pliku wyjściowego)",
    )
    args = parser.parse_args()

    out = Path("assets/templates")
    out.mkdir(parents=True, exist_ok=True)

    try:
        with WindowCapture("Metin2") as wc:  # fragment tytułu
            if not wc.locate(timeout=5):
                raise RuntimeError("Window not found (Nie znaleziono okna)")
            frame = np.array(wc.grab())[:, :, :3]

        x, y, w, h = args.roi
        out_path = out / f"{args.name}.png"
        cv2.imwrite(str(out_path), frame[y : y + h, x : x + w])
        logging.info("Saved template: %s (Zapisano szablon)", out_path)
    except Exception as exc:
        logging.error(
            "Template capture failed: %s (Błąd podczas przechwytywania szablonu)",
            exc,
        )


if __name__ == "__main__":
    main()
