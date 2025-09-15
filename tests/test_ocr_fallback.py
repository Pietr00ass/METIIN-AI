import os
import sys
import types

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class DummyReader:
    def __init__(self, lang, gpu=False):
        self.lang = lang
        self.gpu = gpu

    def readtext(self, frame):
        return []


def _reader(lang, gpu=False):
    if lang == ["en"]:
        return DummyReader(lang, gpu)
    raise RuntimeError("missing lang")


sys.modules["easyocr"] = types.SimpleNamespace(Reader=_reader)

import agent.ocr as ocr_module


def test_ocr_falls_back_to_english():
    ocr = ocr_module.Ocr(["pl"])
    assert ocr.reader.lang == ["en"]
