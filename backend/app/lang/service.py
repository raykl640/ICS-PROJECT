"""Per-request language layer (ARCHITECTURE.md §8.2): sw questions → English for retrieval; answers → sw by section.

Translation is a best-effort aid, not an authoritative legal translation. Citations and numbers are masked in both
directions so they come back byte-identical. An answer segment that loses a placeholder twice is shown in English and
reported to the caller; a question that loses one gets the lost spans appended, since it only feeds retrieval.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.config import Settings
from backend.app.interfaces import Translator
from backend.app.lang.detect import resolve_language
from backend.app.lang.glossary import Glossary, load_glossary
from backend.app.lang.protect import STYLES, Protector, unmask
from backend.app.lang.segment import segment
from backend.app.lang.translator import MarianTranslator
from backend.app.models import Language, ParsedResponse, UserLanguage

_LETTER = re.compile(r"[^\W\d_]")
_SECTION_KEYS = ("rights", "steps", "letter")


@dataclass(frozen=True)
class PreparedQuery:
    """The English text retrieval runs on, the user's language, and whether a translation happened."""

    english: str
    original_lang: UserLanguage
    translated: bool


@dataclass(frozen=True)
class TranslatedSections:
    """The answer in Kiswahili (same three keys) and the English segments that had to stay untranslated."""

    sections_sw: ParsedResponse
    untranslated_segments: list[str] = field(default_factory=list)


class LanguageService:
    """Resolves the question language and translates in both directions with citation protection."""

    def __init__(
        self, sw_en: Translator, en_sw: Translator, act_names: Sequence[str], glossary: Glossary, settings: Settings
    ) -> None:
        self._sw_en = sw_en
        self._en_sw = en_sw
        self._question_protector = Protector(act_names, None)  # glossary renders EN→SW only
        self._answer_protector = Protector(act_names, glossary)
        self._settings = settings

    def prepare_query(self, question: str, ui_lang: Language) -> PreparedQuery:
        """Resolve the language; translate sw→en only when the question is Swahili."""
        s = self._settings
        lang = resolve_language(question, ui_lang, s.lang_min_detect_chars, s.lang_min_detect_prob)
        if lang == "en":
            return PreparedQuery(question, "en", False)
        english, lost = _translate_protected([question], self._sw_en, self._question_protector)[question]
        return PreparedQuery(" ".join([english, *lost]), "sw", True)

    def translate_result(self, sections: ParsedResponse) -> TranslatedSections:
        """Translate rights, steps and letter (headers stay as keys) sentence by sentence, all in one batch."""
        s = self._settings
        layouts = {
            key: segment(getattr(sections, key), s.translate_max_tokens, s.tokens_per_word, pack=False)
            for key in _SECTION_KEYS
        }
        texts = list(dict.fromkeys(p.text for parts in layouts.values() for p in parts if p.translate))
        results = _translate_protected(texts, self._en_sw, self._answer_protector)
        untranslated = [text for text in texts if results[text][1]]
        rendered = {
            key: "".join(results[p.text][0] if p.translate and not results[p.text][1] else p.text for p in parts)
            for key, parts in layouts.items()
        }
        sw = ParsedResponse(**rendered, format_ok=sections.format_ok)
        return TranslatedSections(sw, untranslated)


def _translate_protected(
    texts: list[str], translator: Translator, protector: Protector
) -> dict[str, tuple[str, list[str]]]:
    """Per text: mask, translate (batched), unmask; texts that lose a placeholder are retried once with the next style.

    Returns text → (best translation, source spans still lost); an empty list means every span came back.
    """
    results: dict[str, tuple[str, list[str]]] = {}
    pending = texts
    for style in STYLES:
        if not pending:
            break
        masked = {text: protector.mask(text, style) for text in pending}
        for text, m in masked.items():
            if _LETTER.search(style.pattern.sub("", m.text)) is None:
                results[text] = unmask(m.text, m)  # only citations/numbers/punctuation: nothing for the model to do
        to_model = [text for text in pending if text not in results or results[text][1]]
        for text, output in zip(to_model, translator.translate_batch([masked[t].text for t in to_model]), strict=True):
            results[text] = unmask(output, masked[text])
        pending = [text for text in to_model if results[text][1]]
    return results


def load_language_service(
    settings: Settings, sw_en: Translator | None = None, en_sw: Translator | None = None
) -> LanguageService:
    """Service with the Marian translators (lazy) unless others are injected, and the glossary from settings."""
    return LanguageService(
        sw_en or MarianTranslator("sw-en", settings),
        en_sw or MarianTranslator("en-sw", settings),
        [act.name for act in settings.acts],
        load_glossary(settings.glossary_path),
        settings,
    )


def load_ui_strings(path: Path) -> dict[UserLanguage, dict[str, str]]:
    """EN/SW interface labels from ui_strings.json; both languages must define the same keys."""
    data = json.loads(path.read_text(encoding="utf-8"))
    strings: dict[UserLanguage, dict[str, str]] = {"en": data["en"], "sw": data["sw"]}
    if strings["en"].keys() != strings["sw"].keys():
        raise ValueError(f"{path.name}: en and sw keys differ: {sorted(strings['en'].keys() ^ strings['sw'].keys())}")
    return strings
