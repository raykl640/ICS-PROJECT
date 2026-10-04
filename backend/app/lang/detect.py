"""Question language (ARCHITECTURE.md §8.2): the UI choice is authoritative; "auto" falls back to seeded langdetect."""

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

from backend.app.models import Language, UserLanguage


def detect_lang(text: str, min_chars: int, min_prob: float) -> UserLanguage:
    """Return "sw" only if langdetect is confident the text is Swahili; short, mixed (Sheng) or other text is "en"."""
    if len(text.strip()) < min_chars:
        return "en"
    DetectorFactory.seed = 0  # langdetect samples randomly; a fixed seed makes repeated calls agree
    try:
        best = detect_langs(text)[0]
    except LangDetectException:  # no letters at all
        return "en"
    return "sw" if best.lang == "sw" and best.prob >= min_prob else "en"


def resolve_language(text: str, ui_lang: Language, min_chars: int, min_prob: float) -> UserLanguage:
    """Use the UI choice when it is "en"/"sw"; detect only for "auto"."""
    if ui_lang != "auto":
        return ui_lang
    return detect_lang(text, min_chars, min_prob)
