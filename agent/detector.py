from __future__ import annotations
from typing import List, Dict

import numpy as np
import cv2
from ultralytics import YOLO

# ogranicz wątki OpenCV na Windows (stabilniej na CPU)
cv2.setNumThreads(1)


class ObjectDetector:
    """Lekka nakładka na Ultralytics YOLO do detekcji na klatce BGR (numpy array)."""

    def __init__(self, model_path: str, classes: list[str] | None = None,
                 conf: float = 0.5, iou: float = 0.45, device=None):
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.classes = classes
        self.conf = conf
        self.iou = iou
        self.device = device

    def infer(self, frame_bgr: np.ndarray) -> List[Dict]:
        res = self.model.predict(
            source=frame_bgr,
            verbose=False,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
        )[0]
        out: List[Dict] = []
        names = res.names
        for box in res.boxes:
            cls_id = int(box.cls)
            name = names.get(cls_id, str(cls_id))
            if self.classes and name not in self.classes:
                continue
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
            out.append(
                {
                    "name": name,
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf.cpu().numpy()),
                }
            )
        return out
