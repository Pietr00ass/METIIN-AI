import sys
import types
import pytest


def test_extract_frames_invalid_step(monkeypatch):
    dummy_cv2 = types.SimpleNamespace(
        VideoCapture=lambda *a, **k: types.SimpleNamespace(
            isOpened=lambda: True,
            read=lambda: (False, None),
            release=lambda: None,
        ),
        imwrite=lambda *a, **k: True,
    )
    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setattr(sys, "argv", ["extract_frames", "--step", "0"])
    import importlib
    extract_frames = importlib.import_module("tools.extract_frames")
    with pytest.raises(SystemExit) as exc:
        extract_frames.main()
    assert exc.value.code == 2


def test_extract_frames_missing_rec_dir(monkeypatch, tmp_path):
    dummy_cv2 = types.SimpleNamespace(
        VideoCapture=lambda *a, **k: types.SimpleNamespace(
            isOpened=lambda: True,
            read=lambda: (False, None),
            release=lambda: None,
        ),
        imwrite=lambda *a, **k: True,
    )
    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    missing = tmp_path / "nope"
    monkeypatch.setattr(sys, "argv", ["extract_frames", "--rec-dir", str(missing)])
    import importlib
    sys.modules.pop("tools.extract_frames", None)
    extract_frames = importlib.import_module("tools.extract_frames")
    with pytest.raises(SystemExit) as exc:
        extract_frames.main()
    assert exc.value.code == 2
