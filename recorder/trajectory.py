from __future__ import annotations

"""Trajectory extraction and persistence utilities.

JSON format:
{
  "version": 1,
  "source": "cursor" | "minimap",
  "waypoints": [{"x": 123.4, "y": 456.7, "delay_ms": 120}, ...],
  "meta": {...}
}

NPZ format:
  arrays x, y, delay_ms plus scalar metadata arrays: source, version, meta (JSON string).
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


@dataclass
class Waypoint:
    x: float
    y: float
    delay_ms: int


@dataclass
class Trajectory:
    waypoints: list[Waypoint]
    source: str = "cursor"
    version: int = 1
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "source": self.source,
            "waypoints": [
                {"x": wp.x, "y": wp.y, "delay_ms": wp.delay_ms}
                for wp in self.waypoints
            ],
            "meta": self.meta,
        }


def load_events_jsonl(path: str | Path) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _normalize_events(events: Iterable) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for entry in events:
        if isinstance(entry, dict):
            ts = float(entry.get("ts", 0.0))
            payload = entry.get("payload", {})
        else:
            ts = float(entry[0])
            payload = entry[2] if len(entry) > 2 else {}
        if not isinstance(payload, dict):
            continue
        x = payload.get("x")
        y = payload.get("y")
        if x is None or y is None:
            continue
        points.append((float(x), float(y), ts))
    points.sort(key=lambda p: p[2])
    return points


def _build_waypoints(points: Sequence[tuple[float, float, float]]) -> list[Waypoint]:
    waypoints: list[Waypoint] = []
    for idx, (x, y, ts) in enumerate(points):
        next_ts = points[idx + 1][2] if idx + 1 < len(points) else ts
        delay_ms = int(max(round((next_ts - ts) * 1000), 0))
        waypoints.append(Waypoint(x=x, y=y, delay_ms=delay_ms))
    return waypoints


def trajectory_from_cursor_events(
    events: Iterable,
    min_distance_px: float = 4.0,
    min_delay_ms: int = 25,
) -> Trajectory:
    points = _normalize_events(events)
    filtered: list[tuple[float, float, float]] = []
    last_x = last_y = last_ts = None
    for x, y, ts in points:
        if last_x is None:
            filtered.append((x, y, ts))
            last_x, last_y, last_ts = x, y, ts
            continue
        dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
        delay_ms = int(round((ts - last_ts) * 1000))
        if dist >= min_distance_px or delay_ms >= min_delay_ms:
            filtered.append((x, y, ts))
            last_x, last_y, last_ts = x, y, ts
    return Trajectory(
        waypoints=_build_waypoints(filtered),
        source="cursor",
        meta={
            "min_distance_px": float(min_distance_px),
            "min_delay_ms": int(min_delay_ms),
        },
    )


def trajectory_from_minimap_positions(
    positions: Sequence[tuple[int, int]],
    timestamps: Sequence[float] | None = None,
    min_distance_px: float = 1.0,
) -> Trajectory:
    if timestamps is None:
        timestamps = [float(i) for i in range(len(positions))]
    if len(positions) != len(timestamps):
        raise ValueError("positions and timestamps must have the same length")
    points: list[tuple[float, float, float]] = []
    last_x = last_y = None
    for (x, y), ts in zip(positions, timestamps):
        if last_x is None:
            points.append((float(x), float(y), float(ts)))
            last_x, last_y = x, y
            continue
        dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
        if dist >= min_distance_px:
            points.append((float(x), float(y), float(ts)))
            last_x, last_y = x, y
    return Trajectory(
        waypoints=_build_waypoints(points),
        source="minimap",
        meta={"min_distance_px": float(min_distance_px)},
    )


def save_trajectory_json(traj: Trajectory, path: str | Path) -> str:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(traj.to_dict(), handle, indent=2, ensure_ascii=False)
    return str(out_path)


def save_trajectory_npz(traj: Trajectory, path: str | Path) -> str:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = traj.to_dict()
    waypoints = data.get("waypoints", [])
    xs = np.array([wp["x"] for wp in waypoints], dtype=np.float32)
    ys = np.array([wp["y"] for wp in waypoints], dtype=np.float32)
    delays = np.array([wp["delay_ms"] for wp in waypoints], dtype=np.int32)
    np.savez(
        out_path,
        x=xs,
        y=ys,
        delay_ms=delays,
        source=np.array([data.get("source", "cursor")], dtype=object),
        version=np.array([data.get("version", 1)], dtype=np.int32),
        meta=np.array([json.dumps(data.get("meta", {}))], dtype=object),
    )
    return str(out_path)


def load_trajectory(path: str | Path) -> Trajectory:
    in_path = Path(path)
    if not in_path.exists():
        raise FileNotFoundError(f"trajectory file not found: {in_path}")
    if in_path.suffix.lower() == ".npz":
        data = np.load(in_path, allow_pickle=True)
        xs = data.get("x", np.array([]))
        ys = data.get("y", np.array([]))
        delays = data.get("delay_ms", np.array([]))
        source = str(data.get("source", ["cursor"])[0])
        version = int(data.get("version", [1])[0])
        meta_raw = data.get("meta", ["{}"])[0]
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
        except json.JSONDecodeError:
            meta = {}
        waypoints = [
            Waypoint(x=float(x), y=float(y), delay_ms=int(delay))
            for x, y, delay in zip(xs, ys, delays)
        ]
        return Trajectory(waypoints=waypoints, source=source, version=version, meta=meta)
    with open(in_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    waypoints = [
        Waypoint(
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            delay_ms=int(item.get("delay_ms", 0)),
        )
        for item in payload.get("waypoints", [])
    ]
    return Trajectory(
        waypoints=waypoints,
        source=payload.get("source", "cursor"),
        version=int(payload.get("version", 1)),
        meta=payload.get("meta", {}),
    )


__all__ = [
    "Waypoint",
    "Trajectory",
    "load_events_jsonl",
    "trajectory_from_cursor_events",
    "trajectory_from_minimap_positions",
    "save_trajectory_json",
    "save_trajectory_npz",
    "load_trajectory",
]
