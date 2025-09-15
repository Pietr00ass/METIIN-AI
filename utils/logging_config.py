from __future__ import annotations

from pathlib import Path
import sys

from loguru import logger

from agent import get_config

cfg = get_config()
log_dir = Path(cfg.paths.log_dir or "logs")
log_dir.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(sys.stderr, level=cfg.logging.level.upper())
logger.add(
    log_dir / "agent_{time}.log",
    rotation="1 MB",
    retention=cfg.logging.retention,
    level=cfg.logging.level.upper(),
)

__all__ = ["logger"]
