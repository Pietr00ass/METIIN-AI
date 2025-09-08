"""Extract frames from recorded gameplay videos.

This utility walks through all ``.mp4`` recordings in a directory and saves
every ``step``‑th frame to an output directory.  It replaces ``print`` calls
with Python's :mod:`logging` module and wraps video processing in ``try``/``except``
blocks so issues with individual files do not stop the whole extraction
process.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import cv2

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rec-dir",
        default="data/recordings",
        help="recordings folder (folder z nagraniami)",
    )
    parser.add_argument(
        "--out-dir",
        default="datasets/mt2/images/train",
        help="output frames folder (folder zapisu klatek)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=15,
        help="save every Nth frame (co ile klatek zapisać; przy 15 FPS → 1 kl/s)",
    )
    args = parser.parse_args()

    if args.step <= 0:
        parser.error("--step must be positive")

    rec_dir = Path(args.rec_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not rec_dir.exists():
        parser.error(
            f"Directory not found: {rec_dir} (Nie znaleziono katalogu {rec_dir})"
        )
    videos = sorted(rec_dir.glob("*.mp4"))
    if not videos:
        logging.warning(
            "Directory %s contains no .mp4 files (Katalog %s nie zawiera plików .mp4)",
            rec_dir,
            rec_dir,
        )
        return

    logging.info(
        "Found %d recordings (Znaleziono %d nagrań…)", len(videos), len(videos)
    )
    for vid in videos:
        logging.info("Processing %s (Przetwarzam)", vid)
        try:
            cap = cv2.VideoCapture(str(vid))
            if not cap.isOpened():
                logging.error(
                    "Cannot open file %s, skipping (Nie można otworzyć pliku %s, pomijam)",
                    vid,
                    vid,
                )
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
            logging.info("Saved %d frames (zapisano %d klatek)", saved, saved)
        except Exception as exc:
            logging.error(
                "Error processing %s: %s (Błąd podczas przetwarzania %s: %s)",
                vid,
                exc,
                vid,
                exc,
            )
    logging.info("Done. (Gotowe.)")


if __name__ == "__main__":
    main()
