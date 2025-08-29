from __future__ import annotations

import numpy as np


class ClickPolicy:
    """Prosty model zwracający zerowe przewidywania.

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
