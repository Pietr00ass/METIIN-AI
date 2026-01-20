import random
import time
from agent import get_config

def random_pause(base: float) -> None:
    """Sleep for ``base`` seconds plus random jitter.

    The jitter magnitude is controlled by ``humanizer.pause_jitter`` in the
    configuration.  Negative durations are clamped to zero.
    """
    cfg = get_config()
    jitter = getattr(cfg, "humanizer", None)
    jitter_val = getattr(jitter, "pause_jitter", 0) if jitter else 0
    duration = base + random.uniform(-jitter_val, jitter_val)
    if duration > 0:
        time.sleep(duration)


def jitter_move(dx: float, dy: float, max_jitter: float) -> tuple[float, float]:
    """Return ``(dx, dy)`` offset by random jitter.

    Jitter is sampled uniformly from ``[-max_jitter, max_jitter]`` for both axes.
    """
    jx = random.uniform(-max_jitter, max_jitter)
    jy = random.uniform(-max_jitter, max_jitter)
    return dx + jx, dy + jy


def maybe_micro_pause() -> None:
    """Optionally sleep for a short, human-like micro pause."""
    cfg = get_config()
    humanizer = getattr(cfg, "humanizer", None)
    if not humanizer:
        return
    chance = getattr(humanizer, "micro_pause_chance", 0.0)
    if chance <= 0 or random.random() >= chance:
        return
    min_pause = getattr(humanizer, "micro_pause_min", 0.0)
    max_pause = getattr(humanizer, "micro_pause_max", 0.0)
    if max_pause < min_pause:
        max_pause = min_pause
    duration = random.uniform(min_pause, max_pause)
    if duration > 0:
        time.sleep(duration)


def maybe_mistake_offset(chance: float, max_offset: float) -> tuple[float, float]:
    """Return a small random offset when a mistake is triggered."""
    if chance <= 0 or max_offset <= 0:
        return 0.0, 0.0
    if random.random() < chance:
        return (
            random.uniform(-max_offset, max_offset),
            random.uniform(-max_offset, max_offset),
        )
    return 0.0, 0.0
