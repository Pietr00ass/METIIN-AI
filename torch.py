import numpy as np

Tensor = np.ndarray

def rand(*shape):
    """Return a random array mimicking ``torch.rand``."""
    return np.random.rand(*shape).astype(np.float32)


def inference_mode():
    """Decorator stub that returns the function unchanged."""
    def wrapper(fn):
        return fn
    return wrapper
