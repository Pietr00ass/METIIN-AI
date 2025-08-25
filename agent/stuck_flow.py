from __future__ import annotations
import collections
import cv2
import numpy as np

class FlowStuck:
    def __init__(self, window=0.8, fps=15, min_mag=0.7):
        self.buf = collections.deque(maxlen=int(window * fps))
        self.prev = None
        self.min_mag = min_mag

    def update(self, frame_gray):
        if self.prev is None:
            self.prev = frame_gray
            return False
        flow = cv2.calcOpticalFlowFarneback(self.prev, frame_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag = np.mean(np.linalg.norm(flow, axis=2))
        self.buf.append(mag)
        self.prev = frame_gray
        return len(self.buf) == self.buf.maxlen and (np.mean(self.buf) < self.min_mag)
