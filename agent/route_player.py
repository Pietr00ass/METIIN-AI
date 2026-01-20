from __future__ import annotations

import time
from pathlib import Path

from . import AgentConfig, get_config
from .game_controller import controller as global_controller
from .game_controller import create_controller
from .strategy import AgentStrategy, register
from recorder.trajectory import load_trajectory
from utils.logging_config import logger


@register("route_player")
class RoutePlayer(AgentStrategy):
    """Replay a recorded trajectory by clicking waypoints with delays."""

    def __init__(self, cfg=None, window_capture=None) -> None:
        self.cfg: AgentConfig | None = None
        self.win = None
        self.controller = None
        self.waypoints = []
        self._idx = 0
        self._next_at = 0.0
        self._started = False
        self._finished = False
        if cfg is not None or window_capture is not None:
            self.setup(cfg, window_capture)

    def setup(self, cfg: AgentConfig | dict | None = None, window_capture=None) -> None:
        if cfg is None:
            cfg = get_config()
        elif isinstance(cfg, dict):
            cfg = AgentConfig(**cfg)
        self.cfg = cfg
        self.win = window_capture
        self.controller = global_controller
        if self.controller is None and self.win is not None:
            self.controller = create_controller(self.win, cfg)

        route_cfg = cfg.route
        self.waypoints = []
        self._idx = 0
        self._started = False
        self._finished = False

        if not route_cfg.enabled:
            logger.info("route_player disabled in config")
            return
        if not route_cfg.path:
            logger.warning("route_player path is empty")
            return
        path = Path(route_cfg.path)
        if not path.exists():
            logger.warning("route_player path not found: %s", path)
            return
        traj = load_trajectory(path)
        self.waypoints = list(traj.waypoints)
        logger.info("route_player loaded %s waypoints from %s", len(self.waypoints), path)

    def step(self) -> None:
        if self.cfg is None or self.controller is None:
            return
        if not self.waypoints or self._finished:
            return
        now = time.monotonic()
        if not self._started:
            self._started = True
            self._next_at = now + float(self.cfg.route.start_delay_sec)
            return
        if now < self._next_at:
            return

        wp = self.waypoints[self._idx]
        x, y = float(wp.x), float(wp.y)
        if self.cfg.route.coordinate_mode == "window" and self.win is not None:
            region = getattr(self.win, "region", None)
            if region:
                left, top, _, _ = region
                x += left
                y += top
        if not self.cfg.dry_run:
            self.controller.click(int(x), int(y))
        self._idx += 1
        if self._idx >= len(self.waypoints):
            if self.cfg.route.loop:
                self._idx = 0
                self._next_at = now + float(self.cfg.route.loop_pause_sec)
            else:
                self._finished = True
            return
        delay_sec = max(float(self.waypoints[self._idx - 1].delay_ms) / 1000.0, 0.0)
        self._next_at = now + delay_sec

    def stop(self) -> None:
        self._finished = True


__all__ = ["RoutePlayer"]
