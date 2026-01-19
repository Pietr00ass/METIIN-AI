"""Preview worker thread for GUI."""

from __future__ import annotations

import cv2
import numpy as np
from PySide6 import QtCore

from agent.detector import ObjectDetector
from recorder.window_capture import WindowCapture


class PreviewWorker(QtCore.QThread):
    """Thread that captures frames from a window and optionally overlays detections."""

    frame_ready = QtCore.Signal(np.ndarray)
    status = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, title_substr: str):
        super().__init__()
        self.title = title_substr
        self._stop = False
        self._det: ObjectDetector | None = None
        self._overlay = False
        self._classes: list[str] | None = None

    def configure_overlay(
        self, model_path: str | None, classes: list[str] | None, enabled: bool
    ) -> None:
        """Enable or disable overlay and load the model lazily."""

        self._overlay = enabled
        self._classes = classes
        if enabled and model_path:
            try:
                self._det = ObjectDetector(model_path, classes)
                self.status.emit(QtCore.QCoreApplication.translate("PreviewWorker", "Overlay YOLO aktywny."))
            except Exception as exc:  # pragma: no cover - UI feedback
                self.error.emit(
                    QtCore.QCoreApplication.translate("PreviewWorker", "Błąd YOLO: {exc}").format(exc=exc)
                )
                self._det = None
        else:
            self._det = None

    def run(self) -> None:  # pragma: no cover - runs in a thread
        """Main loop capturing frames from the window and emitting them."""

        try:
            with WindowCapture(self.title) as cap:
                self.status.emit(QtCore.QCoreApplication.translate("PreviewWorker", "Szukam okna…"))
                if not cap.locate(timeout=5):
                    self.status.emit(QtCore.QCoreApplication.translate("PreviewWorker", "Nie znaleziono okna."))
                    return
                self.status.emit(QtCore.QCoreApplication.translate("PreviewWorker", "Znaleziono okno. Podgląd działa."))
                while not self._stop:
                    fr = cap.grab()
                    frame = np.array(fr)[:, :, :3].copy()
                    if self._overlay and self._det:
                        try:
                            dets = self._det.infer(frame)
                            color_map = {
                                "metin": (0, 0, 255),
                                "boss": (0, 215, 255),
                                "mob_aggressive": (0, 128, 255),
                                "mob_neutral": (0, 255, 128),
                                "loot_label": (0, 255, 255),
                                "ore": (255, 0, 255),
                                "fish": (255, 255, 0),
                            }
                            for d in dets:
                                x1, y1, x2, y2 = map(int, d.bbox)
                                color = color_map.get(d.name, (0, 0, 255))
                                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                cv2.putText(
                                    frame,
                                    f"{d.name} {d.conf:.2f}",
                                    (x1, max(12, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    color,
                                    1,
                                )
                        except Exception as exc:  # pragma: no cover - UI feedback
                            self.error.emit(
                                QtCore.QCoreApplication.translate("PreviewWorker", "Overlay YOLO błąd: {exc}").format(exc=exc)
                            )
                    self.frame_ready.emit(frame)
                    self.msleep(33)
        except Exception as exc:  # pragma: no cover - UI feedback
            self.error.emit(
                QtCore.QCoreApplication.translate("PreviewWorker", "Błąd podglądu: {exc}").format(exc=exc)
            )

    def stop(self) -> None:
        self._stop = True


__all__ = ["PreviewWorker"]
