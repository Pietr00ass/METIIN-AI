from __future__ import annotations

import time
from typing import Dict, List

import cv2
import numpy as np
from ultralytics import YOLO

# ogranicz wątki OpenCV na Windows (stabilniej na CPU)
cv2.setNumThreads(1)


class ObjectDetector:
    """Lekka nakładka na Ultralytics YOLO do detekcji na klatce BGR (numpy array).

    Dodatkowo umożliwia ograniczenie częstotliwości detekcji oraz
    dynamiczne skalowanie rozdzielczości wejściowej w celu redukcji
    obciążenia CPU/GPU.
    """

    def __init__(
        self,
        model_path: str,
        classes: list[str] | None = None,
        conf: float = 0.5,
        iou: float = 0.45,
        device=None,
        max_fps: float | None = None,
        dynamic_resize: bool = False,
        min_scale: float = 0.5,
    ):
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.classes = classes
        self.conf = conf
        self.iou = iou
        self.device = device
        # limit detekcji do ``max_fps`` razy na sekundę
        self.max_fps = max_fps
        self._last_infer_time = 0.0
        self._last_result: List[Dict] = []
        # dynamiczne skalowanie rozdzielczości
        self.dynamic_resize = dynamic_resize
        self.min_scale = min_scale
        self.scale = 1.0

    def infer(self, frame_bgr: np.ndarray) -> List[Dict]:
        now = time.time()
        if self.max_fps:
            min_interval = 1.0 / self.max_fps
            if now - self._last_infer_time < min_interval:
                return self._last_result
        self._last_infer_time = now

        frame_in = frame_bgr
        if self.dynamic_resize and self.scale < 1.0:
            h, w = frame_bgr.shape[:2]
            new_w = max(1, int(w * self.scale))
            new_h = max(1, int(h * self.scale))
            frame_in = cv2.resize(frame_bgr, (new_w, new_h))

        start = time.time()
        res = self.model.predict(
            source=frame_in,
            verbose=False,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
        )[0]
        infer_time = time.time() - start

        out: List[Dict] = []
        names = res.names
        for box in res.boxes:
            cls_id = int(box.cls)
            name = names.get(cls_id, str(cls_id))
            if self.classes and name not in self.classes:
                continue
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
            if self.dynamic_resize and self.scale < 1.0:
                # przeskaluj współrzędne do rozmiaru oryginalnego
                x1 /= self.scale
                y1 /= self.scale
                x2 /= self.scale
                y2 /= self.scale
            out.append(
                {
                    "name": name,
                    "bbox": [x1, y1, x2, y2],
                    "conf": float(box.conf.cpu().numpy()),
                }
            )

        self._last_result = out

        if self.dynamic_resize:
            target = 1.0 / self.max_fps if self.max_fps else 0.1
            if infer_time > target and self.scale > self.min_scale:
                self.scale = max(self.min_scale, self.scale * 0.8)
            elif infer_time < target * 0.5 and self.scale < 1.0:
                self.scale = min(1.0, self.scale / 0.8)

        return out
