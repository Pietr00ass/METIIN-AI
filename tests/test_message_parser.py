import os
import sys
import types

# Make repository root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class DummyToken:
    def __init__(self, lemma):
        self.lemma_ = lemma


class DummyNLP:
    def __call__(self, text):
        return [DummyToken(t) for t in text.split()]


fake_spacy = types.SimpleNamespace(load=lambda name: DummyNLP())
fake_pt = types.SimpleNamespace(image_to_string=lambda img, lang="pol": "")

sys.modules["spacy"] = fake_spacy
sys.modules["pytesseract"] = fake_pt

import agent.message_parser as mp

mp._nlp = DummyNLP()


def _set_ocr(text: str) -> None:
    mp.pytesseract.image_to_string = lambda img, lang="pol": text


def test_classifies_no_boss():
    _set_ocr("Brak bossa")
    _, event = mp.parse_message(None)
    assert event == "no boss"


def test_classifies_dungeon_finished():
    _set_ocr("Lochy ukończone")
    _, event = mp.parse_message(None)
    assert event == "dungeon finished"
