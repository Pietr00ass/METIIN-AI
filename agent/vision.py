from __future__ import annotations

"""Lightweight vision helpers for detecting game state overlays.

The real project uses OCR and template matching to recognise game screens.
For the purposes of the tests we implement a tiny template matcher that looks
for small hard coded patterns inside the frame.  The templates are deliberately
minimal so that unit tests can construct frames on the fly without relying on
external assets.
"""

import numpy as np

# Simple 3x3 binary templates.  Values are either 0 or 255 which makes them
# trivial to embed inside dummy frames used by the tests.
LOGGED_OUT_TEMPLATE = np.array(
    [[0, 255, 0], [255, 255, 255], [0, 255, 0]], dtype=np.uint8
)
LOADING_TEMPLATE = np.array(
    [[255, 0, 255], [0, 255, 0], [255, 0, 255]], dtype=np.uint8
)


def _match_template(frame: np.ndarray, template: np.ndarray) -> bool:
    """Return ``True`` if ``template`` is found in ``frame``.

    The matcher operates on the first channel of the image and performs a very
    naive sliding window comparison.  This is more than sufficient for unit
    tests where the frames are tiny and generated synthetically.
    """

    if frame.ndim == 3:
        chan = frame[..., 0]
    else:
        chan = frame
    h, w = template.shape
    fh, fw = chan.shape
    if fh < h or fw < w:
        return False
    for y in range(fh - h + 1):
        for x in range(fw - w + 1):
            if np.array_equal(chan[y : y + h, x : x + w], template):
                return True
    return False


def is_logged_out(frame: np.ndarray) -> bool:
    """Detect the logout screen in ``frame`` using a small template."""

    return _match_template(frame, LOGGED_OUT_TEMPLATE)


def is_loading(frame: np.ndarray) -> bool:
    """Detect the loading screen in ``frame`` using a small template."""

    return _match_template(frame, LOADING_TEMPLATE)


__all__ = ["is_logged_out", "is_loading", "LOGGED_OUT_TEMPLATE", "LOADING_TEMPLATE"]
