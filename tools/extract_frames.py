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

from utils.logging_config import logger


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
        logger.warning(
            "Directory {} contains no .mp4 files (Katalog {} nie zawiera plików .mp4)",
            rec_dir,
            rec_dir,
        )
        return

    logger.info("Found {} recordings (Znaleziono {} nagrań…)", len(videos), len(videos))
    for vid in videos:
        logger.info("Processing {} (Przetwarzam)", vid)
        try:
            cap = cv2.VideoCapture(str(vid))
            if not cap.isOpened():
                logger.error(
                    "Cannot open file {}, skipping (Nie można otworzyć pliku {}, pomijam)",
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
            logger.info("Saved {} frames (zapisano {} klatek)", saved, saved)
        except Exception as exc:
            logger.error(
                "Error processing {}: {} (Błąd podczas przetwarzania {}: {})",
                vid,
                exc,
                vid,
                exc,
            )
    logger.info("Done. (Gotowe.)")


if __name__ == "__main__":
    main()
