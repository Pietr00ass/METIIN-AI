#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import cv2
from ultralytics import YOLO
from utils.logging_config import logger
from utils.classes import YOLO_CLASS_INDEX

# YOLO label (cx, cy, w, h) — wartości znormalizowane do [0, 1]
Box = Tuple[int, float, float, float, float]


def _to_yolo_format(result, width: int, height: int) -> List[Box]:
    """
    Konwersja detekcji YOLO do formatu etykiet (cx, cy, w, h) w skali [0,1].
    """
    boxes: List[Box] = []

    if result is None or result.boxes is None or len(result.boxes) == 0:
        return boxes

    names = result.names or {}
    # xyxy: [x1, y1, x2, y2] w pikselach
    xyxy = result.boxes.xyxy.cpu().numpy()
    cls_ids = result.boxes.cls.cpu().numpy().astype(int)

    # konwersja do (cx, cy, w, h) w pikselach
    cx = (xyxy[:, 0] + xyxy[:, 2]) / 2.0
    cy = (xyxy[:, 1] + xyxy[:, 3]) / 2.0
    w = xyxy[:, 2] - xyxy[:, 0]
    h = xyxy[:, 3] - xyxy[:, 1]

    # normalizacja do [0,1]
    cx /= float(width)
    cy /= float(height)
    w /= float(width)
    h /= float(height)

    for i in range(len(cx)):
        raw_id = int(cls_ids[i])
        if isinstance(names, dict):
            name = names.get(raw_id, str(raw_id))
        elif isinstance(names, (list, tuple)) and raw_id < len(names):
            name = names[raw_id]
        else:
            name = str(raw_id)
        mapped_id = YOLO_CLASS_INDEX.get(name)
        if mapped_id is None:
            logger.debug("Pomijam klasę bez mapowania: {}", name)
            continue
        boxes.append(
            (mapped_id, float(cx[i]), float(cy[i]), float(w[i]), float(h[i]))
        )
    return boxes


def _iter_images(dir_path: Path) -> Iterable[Path]:
    """
    Iteruje po obrazach w katalogu (rekurencyjnie) o rozszerzeniach .jpg/.jpeg/.png.
    """
    exts = (".jpg", ".jpeg", ".png")
    for p in sorted(dir_path.rglob("*")):
        if p.suffix.lower() in exts and p.is_file():
            yield p


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
        help="ścieżka do wag YOLO",
    )
    parser.add_argument(
        "--images",
        required=True,
        help="folder z obrazami",
    )
    parser.add_argument(
        "--labels",
        required=True,
        help="folder zapisu etykiet (.txt)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="próg ufności",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="podgląd i akceptacja",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="pomiń obrazy, które już mają pliki etykiet",
    )

    args = parser.parse_args()

    img_dir = Path(args.images)
    lbl_dir = Path(args.labels)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    if not img_dir.exists():
        parser.error(f"Nie znaleziono katalogu: {img_dir}")

    try:
        model = YOLO(args.model)
    except Exception as exc:
        parser.error(f"Nie można załadować modelu: {exc!r}")

    images = list(_iter_images(img_dir))
    if not images:
        logger.warning("Katalog {} nie zawiera obrazów.", img_dir)
        return

    logger.info("Przetwarzam {} obrazów…", len(images))

    for img_path in images:
        label_path = lbl_dir / f"{img_path.stem}.txt"

        if args.skip_existing and label_path.exists():
            logger.info("Skipping {}", img_path.name)
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            logger.error("Nie można odczytać {}, pomijam.", img_path)
            continue

        result = model(img, conf=args.confidence, verbose=False)[0]
        boxes = _to_yolo_format(result, img.shape[1], img.shape[0])

        # Podgląd i akceptacja wyników
        if args.interactive:
            preview = result.plot()
            cv2.imshow("label-assistant: podgląd", preview)
            logger.info("Naciśnij ENTER lub Y, aby zapisać; inny klawisz — pominiecie.")
            key = cv2.waitKey(0)
            cv2.destroyAllWindows()
            if key not in (ord("y"), ord("Y"), 13):
                logger.info("Pominięto: {}", img_path.name)
                continue

        # Zapis etykiet
        with open(label_path, "w", encoding="utf-8") as f:
            for cls_id, cx, cy, w, h in boxes:
                f.write(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

        logger.info("Zapisano {} (liczba bbox: {})", label_path, len(boxes))


if __name__ == "__main__":
    main()
