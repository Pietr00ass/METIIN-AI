import sys
import types

import pytest
from utils.logging_config import logger


def test_skip_existing(monkeypatch, tmp_path, caplog):
    img_dir = tmp_path / "images"
    lbl_dir = tmp_path / "labels"
    img_dir.mkdir()
    lbl_dir.mkdir()

    img = img_dir / "test.jpg"
    img.write_bytes(b"")
    lbl = lbl_dir / "test.txt"
    lbl.write_text("orig")

    dummy_cv2 = types.SimpleNamespace()
    dummy_ultralytics = types.SimpleNamespace(YOLO=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "cv2", dummy_cv2)
    monkeypatch.setitem(sys.modules, "ultralytics", dummy_ultralytics)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "label_assistant",
            "--model",
            "dummy.pt",
            "--images",
            str(img_dir),
            "--labels",
            str(lbl_dir),
            "--skip-existing",
        ],
    )

    import importlib

    handler_id = logger.add(caplog.handler, format="{message}", level="INFO")
    la = importlib.import_module("tools.label_assistant")
    la.main()
    logger.remove(handler_id)

    assert lbl.read_text() == "orig"
    assert "Skipping test.jpg" in caplog.text
