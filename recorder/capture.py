from __future__ import annotations
import time, json, threading
from datetime import datetime
from pathlib import Path
import cv2
import mss
import numpy as np
from pynput import mouse, keyboard

from agent.keycodes import pynput_key_name

class InputLogger:
    def __init__(self):
        self.buffer = []  # (ts, kind, payload)
        self._lock = threading.Lock()

    def on_click(self, x, y, button, pressed):
        if pressed:
            with self._lock:
                self.buffer.append((time.time(), 'click', {'x': x, 'y': y, 'button': str(button)}))

    def on_press(self, key):
        name = pynput_key_name(key)
        if name is None:
            return
        with self._lock:
            self.buffer.append((time.time(), 'key', {'key': name, 'down': True}))

    def on_release(self, key):
        name = pynput_key_name(key)
        if name is None:
            return
        with self._lock:
            self.buffer.append((time.time(), 'key', {'key': name, 'down': False}))

    def flush(self):
        with self._lock:
            out = list(self.buffer)
            self.buffer.clear()
            return out

def record_session(out_dir: str, region=(0, 0, 1280, 720), fps=15, duration_sec=300):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    video_path = Path(out_dir) / f"rec_{ts}.mp4"
    events_path = Path(out_dir) / f"rec_{ts}.jsonl"

    sct = mss.mss()
    mon = {'left': region[0], 'top': region[1], 'width': region[2], 'height': region[3]}
    vw = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (region[2], region[3]))

    logger = InputLogger()
    ml = mouse.Listener(on_click=logger.on_click); ml.start()
    kl = keyboard.Listener(on_press=logger.on_press, on_release=logger.on_release); kl.start()

    period = 1.0 / fps
    t_end = time.time() + duration_sec
    with open(events_path, 'w', encoding='utf-8') as f:
        while time.time() < t_end:
            t0 = time.time()
            frame = np.array(sct.grab(mon))[:, :, :3]
            vw.write(frame)
            for e in logger.flush():
                f.write(json.dumps({'ts': e[0], 'kind': e[1], 'payload': e[2]}) + "\n")
            dt = time.time() - t0
            if dt < period:
                time.sleep(period - dt)

    vw.release(); ml.stop(); kl.stop()
    return str(video_path), str(events_path)
