from __future__ import annotations

import numpy as np


class KbdPolicy:
    """Prosty model zwracający prawdopodobieństwa klawiszy WASD.

    Zwraca macierz zer o kształcie ``(B, 4)`` odpowiadającą klawiszom
    ``W``, ``A``, ``S`` i ``D``.
    """

    def __init__(self, weights=None) -> None:
        self.weights = weights

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch = x.shape[0]
        return np.zeros((batch, 4), dtype=np.float32)

    __call__ = forward
