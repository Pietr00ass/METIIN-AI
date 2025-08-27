from __future__ import annotations

import argparse
import logging

from ultralytics import YOLO

logging.basicConfig(level=logging.INFO)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Ścieżka do data.yaml")
    ap.add_argument("--model", default="yolov8n.pt", help="Waga startowa (lokalna)")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None, help="cpu | 0 | 0,1 itp.")
    args = ap.parse_args()

    try:
        logging.info("Rozpoczynam trening YOLO na danych %s", args.data)
        y = YOLO(args.model)
        y.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
        )
        logging.info("Trening YOLO zakończony pomyślnie")
    except Exception as exc:
        logging.error("Błąd podczas treningu YOLO: %s", exc)


if __name__ == "__main__":
    main()
