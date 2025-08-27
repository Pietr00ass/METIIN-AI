"""Extract frames from recorded gameplay videos.

This utility walks through all ``.mp4`` recordings in a directory and saves
every ``step``‑th frame to an output directory.  It replaces ``print`` calls
with Python's :mod:`logging` module and wraps video processing in ``try``/``except``
blocks so issues with individual files do not stop the whole extraction
process.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import logging


logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rec-dir", default="data/recordings", help="folder z nagraniami")
    parser.add_argument(
        "--out-dir", default="datasets/mt2/images/train", help="folder zapisu klatek"
    )
    parser.add_argument(
        "--step", type=int, default=15, help="co ile klatek zapisać (przy 15 FPS → 1 kl/s)"
    )
    args = parser.parse_args()

    if args.step <= 0:
        parser.error("--step must be positive")

    rec_dir = Path(args.rec_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rec_dir.exists():
        parser.error(f"Nie znaleziono katalogu {rec_dir}")
    videos = sorted(rec_dir.glob("*.mp4"))
    if not videos:
        logging.warning("Katalog %s nie zawiera plików .mp4", rec_dir)
        return

    logging.info("Znaleziono %d nagrań…", len(videos))
    for vid in videos:
        logging.info("Przetwarzam: %s", vid)
        try:
            cap = cv2.VideoCapture(str(vid))
            if not cap.isOpened():
                logging.error("Nie można otworzyć pliku %s, pomijam", vid)
                continue
            i = 0
            saved = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if i % args.step == 0:
                    out_path = out_dir / f"{vid.stem}_{i:06d}.jpg"
                    cv2.imwrite(str(out_path), frame)
                    saved += 1
                i += 1
            cap.release()
            logging.info(" zapisano %d klatek", saved)
        except Exception as exc:
            logging.error("Błąd podczas przetwarzania %s: %s", vid, exc)
    logging.info("Gotowe.")


if __name__ == "__main__":
    main()

