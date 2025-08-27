from __future__ import annotations
import time, json, threading
from datetime import datetime
from pathlib import Path
import cv2
import mss
import numpy as np
from pynput import mouse

try:  # ``keyboard`` provides low level scan‑code events
    import keyboard as _keyboard
except Exception:  # pragma: no cover - library may be missing on CI
    _keyboard = None

class InputLogger:
    """Collects mouse clicks and raw keyboard scan‑code events."""

    def __init__(self) -> None:
        self.buffer = []  # (ts, kind, payload)
        self._lock = threading.Lock()
        self._kb_hook = None

    # --- mouse -----------------------------------------------------------------
    def on_click(self, x, y, button, pressed):
        if pressed:
            with self._lock:
                self.buffer.append(
                    (time.time(), "click", {"x": x, "y": y, "button": str(button)})
                )

    # --- keyboard --------------------------------------------------------------
    def _on_key_event(self, event):
        """Internal callback used by the ``keyboard`` hook."""
        with self._lock:
            self.buffer.append(
                (
                    time.time(),
                    "key",
                    {"scancode": event.scan_code, "down": event.event_type == "down"},
                )
            )

    def start(self):
        """Begin capturing keyboard events using a low‑level hook."""
        if _keyboard is None:
            raise RuntimeError("keyboard library not available")
        self._kb_hook = _keyboard.hook(self._on_key_event)

    def stop(self):
        if _keyboard is not None and self._kb_hook is not None:
            _keyboard.unhook(self._kb_hook)
            self._kb_hook = None

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
    logger.start()
    ml = mouse.Listener(on_click=logger.on_click)
    ml.start()

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

    vw.release(); ml.stop(); logger.stop()
    return str(video_path), str(events_path)
