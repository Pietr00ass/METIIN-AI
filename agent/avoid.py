from __future__ import annotations
import cv2
import numpy as np

class CollisionAvoid:
    """Ekranowe unikanie kolizji: krawędzie + przepływ w centralnym pasku."""
    def __init__(self, edge_thr=120, flow_mag_thr=0.9, band=(0.45, 0.55), near_ratio=0.25):
        self.prev = None
        self.edge_thr = edge_thr
        self.flow_mag_thr = flow_mag_thr
        self.band = band
        self.near_ratio = near_ratio

    def steer(self, frame_bgr):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        H, W = gray.shape
        x0 = int(W * self.band[0]); x1 = int(W * self.band[1])
        center = gray[:, x0:x1]
        edges = cv2.Canny(center, self.edge_thr, self.edge_thr * 2)
        edge_density = edges[:int(H * self.near_ratio), :].mean() / 255.0
        steer = None
        if self.prev is not None:
            flow = cv2.calcOpticalFlowFarneback(self.prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.linalg.norm(flow, axis=2)
            flow_center = mag[:, x0:x1]
            flow_density = flow_center[:int(H * self.near_ratio), :].mean()
            if edge_density > 0.12 or flow_density < self.flow_mag_thr:
                left_edges = cv2.Canny(gray[:, :x0], self.edge_thr, self.edge_thr * 2).mean()
                right_edges = cv2.Canny(gray[:, x1:], self.edge_thr, self.edge_thr * 2).mean()
                steer = 'right' if left_edges > right_edges else 'left'
        self.prev = gray
        return steer
