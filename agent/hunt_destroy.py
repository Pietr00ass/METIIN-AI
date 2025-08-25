from __future__ import annotations
import time
import numpy as np


from .detector import ObjectDetector
from .targets import pick_target
from .avoid import CollisionAvoid
from .wasd import KeyHold
from .interaction import burst_click


class HuntDestroy:
def __init__(self, cfg, window_capture):
self.win = window_capture
self.det = ObjectDetector(cfg['detector']['model_path'], cfg['detector']['classes'], cfg['detector']['conf_thr'], cfg['detector']['iou_thr'])
self.avoid = CollisionAvoid()
# KeyHold z dry-run + watchdogiem fokusu
self.keys = KeyHold(dry=cfg.get('dry_run', False), active_fn=getattr(self.win, 'is_foreground', None))
self.desired_w = cfg['policy']['desired_box_w']
self.deadzone = cfg['policy']['deadzone_x']
self.priority = cfg.get('priority', ["boss", "metin", "potwory"]) # kolejność z GUI
self.period = 1 / 15


def step(self):
fr = self.win.grab(); frame = np.array(fr)[:, :, :3].copy()
H, W = frame.shape[:2]
dets = self.det.infer(frame)
steer = self.avoid.steer(frame)


# sterowanie
self.keys.release_all()
if steer == 'left':
self.keys.press('a')
elif steer == 'right':
self.keys.press('d')


tgt = pick_target(dets, (W, H), priority_order=self.priority)
if tgt is None:
return


x1, y1, x2, y2 = tgt['bbox']
cx = (x1 + x2) / 2 / W
bw = (x2 - x1) / W


if abs(cx - 0.5) > self.deadzone:
(self.keys.press('d') if cx > 0.5 else self.keys.press('a'))
if bw < self.desired_w * 0.95:
self.keys.press('w')
elif bw > self.desired_w * 1.25:
self.keys.press('s')


if bw >= self.desired_w * 0.9:
left, top, w, h = self.win.region
# w dry-run nie klikamy realnie – burst_click sam używa pyautogui
if hasattr(self.keys, 'dry') and self.keys.dry:
return
burst_click((x1, y1, x2, y2), (left, top, w, h))