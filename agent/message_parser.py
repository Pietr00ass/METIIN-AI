from __future__ import annotations

import pytesseract
import spacy

_nlp = None


def _get_nlp() -> spacy.language.Language:
    """Lazily load the spaCy model for Polish text."""
    global _nlp
    if _nlp is None:  # pragma: no cover - heavy initialisation
        _nlp = spacy.load("pl_core_news_lg")
    return _nlp


def ocr_image(image) -> str:
    """Extract text from ``image`` using Tesseract."""
    return pytesseract.image_to_string(image, lang="pol")


def classify_message(text: str) -> str | None:
    """Return a high-level event name for ``text``.

    Recognises simple game messages such as "no boss" and
    "dungeon finished".  Returns ``None`` when the text does not match
    any known pattern.
    """

    doc = _get_nlp()(text.lower())
    lemmas = {t.lemma_ for t in doc}
    if any(lemma in {"brak", "no"} for lemma in lemmas) and any(
        "boss" in lemma for lemma in lemmas
    ):
        return "no boss"
    if any(lemma.startswith("loch") or lemma == "dungeon" for lemma in lemmas) and any(
        any(key in lemma for key in ("koniec", "ukoń", "finished", "skoń"))
        for lemma in lemmas
    ):
        return "dungeon finished"
    return None


def parse_message(image) -> tuple[str, str | None]:
    """OCR and classify a message contained in ``image``."""
    text = ocr_image(image)
    event = classify_message(text)
    return text, event


__all__ = ["parse_message", "ocr_image", "classify_message"]
