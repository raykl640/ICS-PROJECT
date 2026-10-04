"""MarianTranslator with a spy model: lazy loading, sharing, batching, segmentation; real models only under -m real."""

import subprocess
import sys
from collections.abc import Iterator

import pytest

from backend.app.config import Settings
from backend.app.interfaces import Translator
from backend.app.lang import translator
from backend.app.lang.translator import MarianTranslator, warmup


class SpyModel:
    """Upper-cases every text and records each generate call."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], int, int]] = []

    def generate(self, texts: list[str], num_beams: int, max_new_tokens: int) -> list[str]:
        self.calls.append((texts, num_beams, max_new_tokens))
        return [t.upper() for t in texts]


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, SpyModel]]:
    built: dict[str, SpyModel] = {}

    def build(model_name: str) -> SpyModel:
        built[model_name] = SpyModel()
        return built[model_name]

    monkeypatch.setattr(translator, "_build_model", build)
    monkeypatch.setattr(translator, "_MODELS", {})
    yield built


def test_importing_the_module_loads_no_ml_library() -> None:
    code = "import sys, backend.app.lang.translator; print(sorted({'torch', 'transformers'} & set(sys.modules)))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_model_loads_lazily_once_and_is_shared(loads: dict[str, SpyModel]) -> None:
    first = MarianTranslator("en-sw", Settings())
    assert isinstance(first, Translator)
    assert loads == {}
    assert first.translate("") == ""
    assert first.translate(" \n ") == " \n "
    assert loads == {}
    first.translate("Hello.")
    MarianTranslator("en-sw", Settings()).translate("Again.")
    assert list(loads) == [Settings().translator_en_sw]
    assert len(loads[Settings().translator_en_sw].calls) == 2


def test_direction_selects_model(loads: dict[str, SpyModel]) -> None:
    settings = Settings(translator_sw_en="sw-model", translator_en_sw="en-model")
    assert MarianTranslator("sw-en", settings).model_name == "sw-model"
    assert MarianTranslator("en-sw", settings).model_name == "en-model"


def test_translate_keeps_layout_and_uses_settings(loads: dict[str, SpyModel]) -> None:
    settings = Settings(translate_num_beams=3, translate_max_new_tokens=99)
    out = MarianTranslator("en-sw", settings).translate("Dear Sir,\n\n1. Ask why.\n2. Keep copies.\n")
    assert out == "DEAR SIR,\n\n1. ASK WHY.\n2. KEEP COPIES.\n"
    (texts, beams, max_new) = loads[settings.translator_en_sw].calls[0]
    assert (texts, beams, max_new) == (["Dear Sir,", "Ask why.", "Keep copies."], 3, 99)


def test_batches_respect_batch_size(loads: dict[str, SpyModel]) -> None:
    settings = Settings(translate_batch_size=2)
    out = MarianTranslator("sw-en", settings).translate_batch(["a", "b", "c", "d", "e"])
    assert out == ["A", "B", "C", "D", "E"]
    assert [len(c[0]) for c in loads[settings.translator_sw_en].calls] == [2, 2, 1]


def test_long_text_is_segmented_under_the_token_limit(loads: dict[str, SpyModel]) -> None:
    settings = Settings(translate_max_tokens=20)
    text = " ".join(f"Sentence {n} is short enough." for n in range(12))
    MarianTranslator("en-sw", settings).translate(text)
    sent = loads[settings.translator_en_sw].calls[0][0]
    assert len(sent) > 1
    assert " ".join(sent) == text


@pytest.mark.parametrize("direction", ["sw-en", "en-sw"])
def test_warmup_translates_one_sentence(loads: dict[str, SpyModel], direction: translator.Direction) -> None:
    warmup(direction, Settings())
    assert len(next(iter(loads.values())).calls) == 1


@pytest.mark.real
def test_real_marian_models_translate_and_keep_section_41() -> None:
    from backend.app.lang.service import load_language_service
    from backend.app.models import ParsedResponse

    settings = Settings()
    service = load_language_service(settings)
    sw_sentences = [
        "Mwajiri wangu alinifukuza kazi bila notisi.",
        "Je, Section 41 inasema nini kuhusu kufukuzwa kazi?",
        "Polisi walinikamata bila kibali.",
    ]
    english = [service.prepare_query(s, "sw").english for s in sw_sentences]
    assert "Section 41" in english[1]
    assert all(e and e != s for e, s in zip(english, sw_sentences, strict=True))

    rights = "Your employer must give you notice. Section 41 requires a hearing. You may complain to a court."
    result = service.translate_result(ParsedResponse(rights=rights))
    assert result.untranslated_segments == []
    assert "Section 41" in result.sections_sw.rights
    assert result.sections_sw.rights != rights
