from __future__ import annotations

import logging
from typing import Callable

import pytesseract
import spacy

_nlp = None


def _get_nlp() -> spacy.language.Language:
    """Lazily load the spaCy model for Polish text."""
    global _nlp
    if _nlp is None:  # pragma: no cover - heavy initialisation
        _nlp = spacy.load("pl_core_news_lg")
    return _nlp


def _contains_any(lemmas: set[str], *subs: str) -> bool:
    """Return True when any ``subs`` substring is present in ``lemmas``."""
    return any(any(sub in lemma for sub in subs) for lemma in lemmas)


# Mapping of high level events to rule predicates operating on token lemmas.
_RULES: dict[str, Callable[[set[str]], bool]] = {
    "no boss": lambda lemmas: (
        any(lemma in {"brak", "no"} for lemma in lemmas)
        and _contains_any(lemmas, "boss")
    ),
    "dungeon finished": lambda lemmas: (
        _contains_any(lemmas, "loch", "dungeon")
        and _contains_any(lemmas, "koniec", "ukoń", "finished", "skoń")
    ),
    "death": lambda lemmas: _contains_any(lemmas, "zgin", "umar", "dead"),
    "inventory full": lambda lemmas: (
        _contains_any(lemmas, "ekwipunek", "inventory")
        and _contains_any(lemmas, "pełn", "full")
    ),
}


def ocr_image(image) -> str:
    """Extract text from ``image`` using Tesseract."""

    try:
        return pytesseract.image_to_string(image, lang="pol")
    except pytesseract.TesseractNotFoundError:
        logging.getLogger(__name__).error(
            "Tesseract OCR binary not found. Install Tesseract and ensure it is available on the system PATH."
        )
        raise


def classify_message(text: str) -> str | None:
    """Return a high-level event name for ``text``.

    Recognises simple game messages such as "no boss" and
    "dungeon finished".  Returns ``None`` when the text does not match
    any known pattern.
    """

    doc = _get_nlp()(text.lower())
    lemmas = {t.lemma_ for t in doc}
    for event, rule in _RULES.items():
        try:
            if rule(lemmas):
                return event
        except Exception:  # pragma: no cover - defensive
            continue
    return None


def parse_message(image) -> tuple[str, str | None]:
    """OCR and classify a message contained in ``image``."""
    text = ocr_image(image)
    event = classify_message(text)
    return text, event


__all__ = ["parse_message", "ocr_image", "classify_message"]
