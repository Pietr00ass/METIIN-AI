from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from agent.wasd import REVERSE_SCANCODES


WASD_KEYS = ("w", "a", "s", "d")


def _extract_key(payload: dict) -> str | None:
    """Return canonical key name from an event payload or ``None``."""
    key = payload.get("key")
    if key:
        return key if key in WASD_KEYS else None
    sc = payload.get("scancode")
    if sc is not None:
        key = REVERSE_SCANCODES.get(sc)
        if key in WASD_KEYS:
            return key
    return None


def align(video_path: str, events_path: str, out_dir: str) -> None:
    """Align recorded video frames with WASD key states.

    For each frame of ``video_path`` a corresponding ``*.npz`` file is written
    to ``out_dir`` containing the image (resized to 224x224) and a four-element
    array indicating the pressed state of ``[w, a, s, d]`` keys.
    """

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Load and preprocess key events
    with open(events_path, "r", encoding="utf-8") as f:
        raw_events = [json.loads(line) for line in f]

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 1.0

    events = []
    for e in raw_events:
        if e.get("kind") != "key":
            continue
        key = _extract_key(e["payload"])
        if key is None:
            continue
        frame_idx = int(e["ts"] * fps) - 1
        events.append((frame_idx, key, e["payload"].get("down", False)))
    events.sort()

    pressed = {k: 0.0 for k in WASD_KEYS}
    ev_i = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # apply all events up to current frame index
        while ev_i < len(events) and events[ev_i][0] <= frame_idx:
            _, key, down = events[ev_i]
            pressed[key] = 1.0 if down else 0.0
            ev_i += 1
        img = cv2.resize(frame, (224, 224))
        y = np.array([pressed[k] for k in WASD_KEYS], dtype=float)
        np.savez_compressed(out / f"{frame_idx:04d}.npz", img=img, y=y)
        frame_idx += 1

    cap.release()
