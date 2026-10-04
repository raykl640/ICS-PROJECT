"""Language resolution: UI choice wins, "auto" uses seeded langdetect with a length guard (invented sentences)."""

import pytest

from backend.app.lang.detect import detect_lang, resolve_language
from backend.app.models import Language

SW = "Mwajiri wangu alinifukuza kazi bila notisi yoyote. Nina haki gani kisheria?"
EN = "My employer dismissed me without any notice. What are my rights under the law?"
SHENG = "Boss ameni-fire bila notice, sasa what do I do na rent iko due?"
FR = "Mon employeur m'a licencié sans préavis. Quels sont mes droits selon la loi?"
SHORT_SW = "Nina haki gani?"

MIN_CHARS = 20
MIN_PROB = 0.7


def _resolve(text: str, ui_lang: Language) -> str:
    return resolve_language(text, ui_lang, MIN_CHARS, MIN_PROB)


@pytest.mark.parametrize(
    ("ui_lang", "text", "expected"),
    [
        ("en", SW, "en"),
        ("en", EN, "en"),
        ("en", SHENG, "en"),
        ("sw", SW, "sw"),
        ("sw", EN, "sw"),
        ("sw", SHENG, "sw"),
        ("sw", SHORT_SW, "sw"),
        ("auto", SW, "sw"),
        ("auto", EN, "en"),
        ("auto", SHENG, "en"),
        ("auto", FR, "en"),
        ("auto", SHORT_SW, "en"),
        ("auto", "", "en"),
        ("auto", "1234567890 !!! 1234567890 ???", "en"),
    ],
)
def test_resolution_matrix(ui_lang: Language, text: str, expected: str) -> None:
    assert _resolve(text, ui_lang) == expected


def test_short_text_guard_applies_before_detection() -> None:
    assert len(SHORT_SW) < MIN_CHARS
    assert detect_lang(SHORT_SW, MIN_CHARS, MIN_PROB) == "en"
    assert detect_lang(SHORT_SW, 0, MIN_PROB) == "sw"


def test_seeded_detection_is_deterministic() -> None:
    texts = [SW, EN, SHENG, FR]
    first = [detect_lang(t, MIN_CHARS, MIN_PROB) for t in texts]
    assert all([detect_lang(t, MIN_CHARS, MIN_PROB) for t in texts] == first for _ in range(20))


def test_min_prob_above_one_never_detects_swahili() -> None:
    assert detect_lang(SW, MIN_CHARS, 1.01) == "en"
