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
