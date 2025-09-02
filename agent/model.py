from __future__ import annotations

import numpy as np


class ClickPolicy:
    """Simple model returning zero predictions.

    In this test implementation we avoid PyTorch; instead we operate on
    ``numpy`` arrays and return matrices of the appropriate shapes.

    PL:
    Prosty model zwracający zerowe przewidywania.

    W implementacji testowej nie używamy PyTorcha; zamiast tego działamy na
    tablicach ``numpy`` i zwracamy macierze o odpowiednich kształtach.
    """

    def __init__(self, weights=None) -> None:
        self.weights = weights

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        batch = x.shape[0]
        point = np.zeros((batch, 2), dtype=np.float32)
        click = np.zeros((batch, 1), dtype=np.float32)
        return point, click

    __call__ = forward
