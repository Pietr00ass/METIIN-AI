import importlib
import os
import sys

sys.modules.pop("cv2", None)
sys.modules.pop("agent.template_matcher", None)
cv2 = importlib.import_module("cv2")
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.template_matcher import TemplateMatcher


def write_template(tmp_path, name="tpl"):
    tpl = np.zeros((10, 10), dtype=np.uint8)
    tpl[2:8, 3:7] = 255
    cv2.imwrite(str(tmp_path / f"{name}.png"), tpl)
    return tpl


def frame_with_template(tpl, x, y, scale=1.0):
    tpl_blur = cv2.GaussianBlur(tpl, (3, 3), 0)
    if scale != 1.0:
        tpl_blur = cv2.resize(
            tpl_blur,
            (int(tpl_blur.shape[1] * scale), int(tpl_blur.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
    h, w = tpl_blur.shape
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    tpl_bgr = np.repeat(tpl_blur[:, :, None], 3, axis=2)
    frame[y : y + h, x : x + w] = tpl_bgr
    return frame, w, h


def test_find_basic(tmp_path):
    tpl = write_template(tmp_path)
    frame, w, h = frame_with_template(tpl, 20, 15)
    tm = TemplateMatcher(templates_dir=str(tmp_path))
    match = tm.find(frame, "tpl", thresh=0.9)
    assert match is not None
    assert match.rect == (20, 15, w, h)
    assert match.center == (20 + w // 2, 15 + h // 2)
    assert match.score > 0.99


def test_find_multi_scale(tmp_path):
    tpl = write_template(tmp_path)
    frame, w, h = frame_with_template(tpl, 10, 12, scale=1.2)
    tm = TemplateMatcher(templates_dir=str(tmp_path))
    match = tm.find(
        frame,
        "tpl",
        thresh=0.9,
        multi_scale=True,
        scales=(1.2, 1.0, 0.8),
    )
    assert match is not None
    assert match.rect == (10, 12, w, h)
    assert match.center == (10 + w // 2, 12 + h // 2)


def test_find_roi_outside(tmp_path):
    tpl = write_template(tmp_path)
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    tm = TemplateMatcher(templates_dir=str(tmp_path))
    with pytest.raises(ValueError):
        tm.find(frame, "tpl", roi=(30, 30, 10, 10))


def test_find_all_multi(tmp_path):
    tpl = write_template(tmp_path)
    tpl_blur = cv2.GaussianBlur(tpl, (3, 3), 0)
    tpl_small = cv2.resize(
        tpl_blur, (int(tpl_blur.shape[1] * 0.8), int(tpl_blur.shape[0] * 0.8)),
        interpolation=cv2.INTER_AREA,
    )
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    tpl_bgr = np.repeat(tpl_blur[:, :, None], 3, axis=2)
    frame[5 : 5 + tpl_blur.shape[0], 5 : 5 + tpl_blur.shape[1]] = tpl_bgr
    tpl_bgr_small = np.repeat(tpl_small[:, :, None], 3, axis=2)
    frame[40 : 40 + tpl_small.shape[0], 30 : 30 + tpl_small.shape[1]] = tpl_bgr_small

    tm = TemplateMatcher(templates_dir=str(tmp_path))
    matches = tm.find_all(
        frame,
        "tpl",
        thresh=0.8,
        multi_scale=True,
        scales=(1.0, 0.8),
    )
    assert len(matches) == 2
    assert matches[0].rect == (5, 5, tpl_blur.shape[1], tpl_blur.shape[0])
    assert matches[1].rect == (30, 40, tpl_small.shape[1], tpl_small.shape[0])


def test_find_all_roi_outside(tmp_path):
    tpl = write_template(tmp_path)
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    tm = TemplateMatcher(templates_dir=str(tmp_path))
    with pytest.raises(ValueError):
        tm.find_all(frame, "tpl", roi=(25, 0, 10, 10))
