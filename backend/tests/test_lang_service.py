"""LanguageService with fake translators: query preparation, section-wise translation, citation protection, fallback."""

import json
import re
from pathlib import Path

import pytest

from backend.app.config import DISCLAIMER, FALLBACK_MESSAGE, Settings
from backend.app.lang.glossary import Glossary
from backend.app.lang.service import LanguageService, load_language_service, load_ui_strings
from backend.app.models import ParsedResponse
from backend.tests.fakes import FakeTranslator

SETTINGS = Settings()
GLOSSARY = Glossary("needs_human_review", {"notice": "notisi", "employer": "mwajiri"})
ACT_NAMES = ["Employment Act", "Constitution of Kenya"]
SW_QUESTION = "Mwajiri wangu alinifukuza kazi bila notisi yoyote. Nina haki gani kisheria?"
EN_QUESTION = "My employer dismissed me without any notice. What are my rights?"
CITATIONS = ["Employment Act, 2007", "Section 41(2)", "s. 45", "Article 41", "Constitution of Kenya", "30", "Cap 226"]
ANSWER = ParsedResponse(
    rights=(
        "Your employer must give notice (Employment Act, 2007, Section 41(2)). Dismissal without a valid reason is "
        "unfair under s. 45.\nArticle 41 of the Constitution of Kenya protects fair labour practices."
    ),
    steps="1. Write to your employer within 30 days.\n2. Report to the Labour Officer under Cap 226.",
    letter="Dear [Recipient],\n\nI write about my dismissal.\n\nYours faithfully,\n[Your Name]",
    format_ok=False,
)


class SpyTranslator(FakeTranslator):
    """FakeTranslator that records its inputs."""

    def __init__(self, tag: str = "sw") -> None:
        super().__init__(tag, {"dismissal": "kufukuzwa", "write": "andika", "dear": "mpendwa"})
        self.inputs: list[str] = []

    def translate(self, text: str) -> str:
        self.inputs.append(text)
        return super().translate(text)


class DroppingTranslator(SpyTranslator):
    """Drops every placeholder matching the given pattern, as a real model sometimes does."""

    def __init__(self, drop: str) -> None:
        super().__init__()
        self.drop = re.compile(drop)

    def translate(self, text: str) -> str:
        return self.drop.sub("", super().translate(text))


def _service(sw_en: SpyTranslator | None = None, en_sw: SpyTranslator | None = None) -> LanguageService:
    return LanguageService(sw_en or SpyTranslator("en"), en_sw or SpyTranslator(), ACT_NAMES, GLOSSARY, SETTINGS)


def test_english_question_skips_translation() -> None:
    sw_en = SpyTranslator("en")
    prepared = _service(sw_en=sw_en).prepare_query(EN_QUESTION, "auto")
    assert (prepared.english, prepared.original_lang, prepared.translated) == (EN_QUESTION, "en", False)
    assert _service(sw_en=sw_en).prepare_query(SW_QUESTION, "en").translated is False
    assert sw_en.inputs == []


@pytest.mark.parametrize("ui_lang", ["sw", "auto"])
def test_swahili_question_is_translated_to_english(ui_lang: str) -> None:
    sw_en = SpyTranslator("en")
    prepared = _service(sw_en=sw_en).prepare_query(SW_QUESTION, ui_lang)  # type: ignore[arg-type]
    assert prepared.original_lang == "sw"
    assert prepared.translated is True
    assert prepared.english == f"[en] {SW_QUESTION}"
    assert sw_en.inputs == [SW_QUESTION]


def test_question_citations_are_masked_but_glossary_is_not_applied() -> None:
    sw_en = SpyTranslator("en")
    question = "Je, Section 41 ya Employment Act inasema nini kuhusu notice ya siku 30?"
    prepared = _service(sw_en=sw_en).prepare_query(question, "sw")
    assert sw_en.inputs == ["Je, ZX0Q ya ZX1Q inasema nini kuhusu notice ya siku ZX2Q?"]
    assert prepared.english == "[en] Je, Section 41 ya Employment Act inasema nini kuhusu notice ya siku 30?"


def test_question_citations_lost_twice_are_appended_for_retrieval() -> None:
    sw_en = DroppingTranslator(r"ZX\d+Q|#\d+")
    prepared = _service(sw_en=sw_en).prepare_query("Je, Section 41 inasema nini kuhusu kufukuzwa?", "sw")
    assert prepared.english == "[sw] Je,  inasema nini kuhusu kufukuzwa? Section 41"


def test_sections_are_translated_separately_and_keep_keys() -> None:
    en_sw = SpyTranslator()
    result = _service(en_sw=en_sw).translate_result(ANSWER)
    sw = result.sections_sw
    assert result.untranslated_segments == []
    assert sw.format_ok is False
    assert sw.rights.startswith("[sw] Your ")
    assert sw.steps.startswith("1. [sw] ")
    assert "\n2. [sw] " in sw.steps
    assert sw.letter.startswith("[sw] mpendwa [Recipient],\n\n")
    assert not any("RIGHTS" in text or "##" in text for text in en_sw.inputs)


def test_round_trip_keeps_every_citation_byte_identical() -> None:
    sw = _service().translate_result(ANSWER).sections_sw
    joined = "\n".join([sw.rights, sw.steps, sw.letter])
    for citation in CITATIONS:
        assert citation in joined


def test_translator_never_sees_citations_and_glossary_renders_bracketed() -> None:
    en_sw = SpyTranslator()
    sw = _service(en_sw=en_sw).translate_result(ANSWER).sections_sw
    sent = "\n".join(en_sw.inputs)
    assert not any(c in sent for c in ["Section 41", "Employment Act", "Article 41", "30", "226"])
    assert "mwajiri [employer]" in sw.rights
    assert "notisi [notice]" in sw.rights


def test_lost_placeholder_is_retried_with_the_next_style() -> None:
    en_sw = DroppingTranslator(r"ZX\d+Q")
    result = _service(en_sw=en_sw).translate_result(ParsedResponse(rights="See Section 41 today."))
    assert result.untranslated_segments == []
    assert result.sections_sw.rights == "[sw] See Section 41 today."
    assert en_sw.inputs == ["See ZX0Q today.", "See #0 today."]


def test_segment_that_keeps_losing_placeholders_stays_english() -> None:
    en_sw = DroppingTranslator(r"ZX\d+Q|#\d+")
    answer = ParsedResponse(rights="Read the contract.\nSee Section 41 today.")
    result = _service(en_sw=en_sw).translate_result(answer)
    assert result.sections_sw.rights == "[sw] Read the contract.\nSee Section 41 today."
    assert result.untranslated_segments == ["See Section 41 today."]


def test_segment_of_only_citations_is_not_sent_to_the_model() -> None:
    en_sw = SpyTranslator()
    result = _service(en_sw=en_sw).translate_result(ParsedResponse(rights="Section 41(2), 2007.", letter=""))
    assert result.sections_sw.rights == "Section 41(2), 2007."
    assert en_sw.inputs == []


def test_load_language_service_uses_settings_glossary_and_acts() -> None:
    service = load_language_service(SETTINGS, SpyTranslator("en"), SpyTranslator())
    rights = service.translate_result(ParsedResponse(rights="The tenant relies on the Employment Act.")).sections_sw
    assert "mpangaji [tenant]" in rights.rights
    assert "Employment Act" in rights.rights


def test_load_language_service_defaults_to_lazy_marian() -> None:
    service = load_language_service(SETTINGS)
    assert service.prepare_query(EN_QUESTION, "en").translated is False


def test_ui_strings_match_config_and_flag_swahili_for_review() -> None:
    strings = load_ui_strings(SETTINGS.ui_strings_path)
    raw = json.loads(SETTINGS.ui_strings_path.read_text(encoding="utf-8"))
    assert raw["status"] == "needs_human_review"
    assert strings["en"]["disclaimer"] == DISCLAIMER
    assert strings["en"]["fallback"] == FALLBACK_MESSAGE
    assert strings["sw"]["fallback"].startswith("Siwezi kupata kifungu mahususi")
    for key in ("tab_rights", "tab_steps", "tab_letter", "disclaimer", "submit", "untranslated_note"):
        assert strings["sw"][key] and strings["sw"][key] != strings["en"][key]


def test_ui_strings_with_mismatched_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "ui.json"
    path.write_text(json.dumps({"en": {"a": "A", "b": "B"}, "sw": {"a": "A"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="'b'"):
        load_ui_strings(path)


def test_only_the_failing_sentence_stays_english() -> None:
    en_sw = DroppingTranslator(r"ZX1Q|#1\b")
    rights = "Read the contract. See Section 41 or s. 45 today. Then write."
    result = _service(en_sw=en_sw).translate_result(ParsedResponse(rights=rights))
    assert result.untranslated_segments == ["See Section 41 or s. 45 today."]
    assert result.sections_sw.rights == "[sw] Read the contract. See Section 41 or s. 45 today. [sw] Then andika."


class BatchCounter(SpyTranslator):
    """Counts translate_batch calls."""

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    def translate_batch(self, texts: list[str]) -> list[str]:
        self.batches.append(texts)
        return super().translate_batch(texts)


def test_all_sections_go_to_the_model_in_one_batch() -> None:
    en_sw = BatchCounter()
    _service(en_sw=en_sw).translate_result(ANSWER)
    assert len(en_sw.batches) == 1
    assert len(en_sw.batches[0]) == len(set(en_sw.batches[0])) > 5


def test_letter_placeholders_stay_for_the_user() -> None:
    en_sw = SpyTranslator()
    letter = "Dear [Recipient],\n\nYours faithfully,\n[Your Name]"
    sw = _service(en_sw=en_sw).translate_result(ParsedResponse(letter=letter)).sections_sw
    assert sw.letter == "[sw] mpendwa [Recipient],\n\n[sw] Yours faithfully,\n[Your Name]"
    assert en_sw.inputs == ["Dear ZX0Q,", "Yours faithfully,"]


def test_shipped_glossary_keeps_letter_closings_away_from_the_model() -> None:
    en_sw = SpyTranslator()
    service = load_language_service(SETTINGS, SpyTranslator("en"), en_sw)
    sw = service.translate_result(ParsedResponse(letter="Yours faithfully,\n[Your Name]")).sections_sw
    assert sw.letter == "wako mwaminifu [Yours faithfully],\n[Your Name]"
    assert en_sw.inputs == []
