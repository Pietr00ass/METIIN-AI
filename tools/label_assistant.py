"""Semi-automatic labeling assistant using a YOLO model.

This utility iterates over all images in a folder, runs a YOLO detector
on each and writes the predictions in the YOLO text format.  With the
``--interactive`` flag the user can accept or skip detections after seeing
a preview window.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List, Tuple

import cv2
from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)

Box = Tuple[int, float, float, float, float]


def _to_yolo_format(result, width: int, height: int) -> List[Box]:
    boxes: List[Box] = []
    if not result.boxes:
        return boxes
    xyxy = result.boxes.xyxy.cpu().numpy()
    cls = result.boxes.cls.cpu().numpy().astype(int)
    for (x1, y1, x2, y2), c in zip(xyxy, cls):
        cx = ((x1 + x2) / 2) / width
        cy = ((y1 + y2) / 2) / height
        w = (x2 - x1) / width
        h = (y2 - y1) / height
        boxes.append((int(c), cx, cy, w, h))
    return boxes


def _iter_images(dir_path: Path) -> Iterable[Path]:
    exts = {".jpg", ".jpeg", ".png"}
    for p in sorted(dir_path.iterdir()):
        if p.suffix.lower() in exts:
            yield p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        required=True,
        help="path to YOLO weights (ścieżka do wag YOLO)",
    )
    parser.add_argument(
        "--images",
        required=True,
        help="images folder (folder z obrazami)",
    )
    parser.add_argument(
        "--labels",
        required=True,
        help="labels output folder (.txt) (folder zapisu etykiet (.txt))",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="confidence threshold (próg ufności)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="preview and accept (podgląd i akceptacja)",
    )
    args = parser.parse_args()

    img_dir = Path(args.images)
    lbl_dir = Path(args.labels)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    if not img_dir.exists():
        parser.error(
            f"Directory not found: {img_dir} (Nie znaleziono katalogu {img_dir})"
        )

    try:
        model = YOLO(args.model)
    except Exception as exc:
        parser.error(f"Cannot load model: {exc} (Nie można załadować modelu: {exc})")

    images = list(_iter_images(img_dir))
    if not images:
        logging.warning(
            "Directory %s contains no images (Katalog %s nie zawiera obrazów)",
            img_dir,
            img_dir,
        )
        return

    logging.info(
        "Processing %d images… (Przetwarzam %d obrazów…)",
        len(images),
        len(images),
    )
    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            logging.error(
                "Cannot read %s, skipping (Nie można odczytać %s, pomijam)",
                img_path,
                img_path,
            )
            continue
        result = model(img, conf=args.confidence, verbose=False)[0]
        boxes = _to_yolo_format(result, img.shape[1], img.shape[0])

        if args.interactive:
            preview = result.plot()
            cv2.imshow("label-assistant", preview)
            key = cv2.waitKey(0)
            cv2.destroyAllWindows()
            if key not in (ord("y"), ord("Y"), 13, 32):
                logging.info("Skipped %s (Pominięto)", img_path.name)
                continue

        label_path = lbl_dir / f"{img_path.stem}.txt"
        with label_path.open("w", encoding="utf-8") as f:
            for c, cx, cy, w, h in boxes:
                f.write(f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
        logging.info(
            "Saved %s (%d boxes) (Zapisano %s (%d boxów))",
            label_path,
            len(boxes),
            label_path,
            len(boxes),
        )
    logging.info("Done. (Gotowe.)")


if __name__ == "__main__":
    main()
