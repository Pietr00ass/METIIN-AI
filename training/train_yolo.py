from __future__ import annotations

import argparse
import logging

from ultralytics import YOLO


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data", required=True, help="path to data.yaml (Ścieżka do data.yaml)"
    )
    ap.add_argument(
        "--model",
        default="yolov8n.pt",
        help="initial weights (Waga startowa, lokalna)",
    )
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument(
        "--device",
        default=None,
        help="device: cpu | 0 | 0,1 etc. (cpu | 0 | 0,1 itp.)",
    )
    args = ap.parse_args()

    try:
        logging.info(
            "Starting YOLO training on %s (Rozpoczynam trening YOLO na danych %s)",
            args.data,
            args.data,
        )
        y = YOLO(args.model)
        y.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
        )
        logging.info(
            "YOLO training completed successfully (Trening YOLO zakończony pomyślnie)"
        )
    except Exception as exc:
        logging.error(
            "YOLO training failed: %s (Błąd podczas treningu YOLO: %s)",
            exc,
            exc,
        )


if __name__ == "__main__":
    main()
