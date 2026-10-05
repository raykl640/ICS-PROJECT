"""What the API is built from: settings plus every heavy component behind its interface (fakes injectable)."""

import dataclasses
import os
from collections.abc import Callable
from dataclasses import dataclass

from backend.app.config import Settings
from backend.app.generation.llm import OllamaClient
from backend.app.interfaces import CrossEncoderLike, Embedder, LLMClient, Translator
from backend.app.lang.service import LanguageService, load_language_service
from backend.app.laws.catalog import LawCatalog, load_catalog
from backend.app.models import ParsedResponse
from backend.app.retrieval.pipeline import ContextPipeline, load_pipeline
from backend.app.retrieval.refs import RefExtractor
from backend.app.retrieval.router import Router

WARMUP_EN = "My employer dismissed me without notice."
WARMUP_SW = "Mwajiri wangu alinifukuza kazi bila notisi."


@dataclass(frozen=True)
class Deps:
    """Components for create_app; load_pipeline runs at startup (indexes + models), the rest is cheap to build.

    setup_logging makes startup install the JSON log handler (the uvicorn entry point; tests keep pytest's logging).
    """

    settings: Settings
    llm: LLMClient
    language: LanguageService
    refs: RefExtractor
    load_pipeline: Callable[[], ContextPipeline]
    load_laws: Callable[[], LawCatalog]
    setup_logging: bool = False


def real_deps(
    settings: Settings,
    *,
    embedder: Embedder | None = None,
    reranker: CrossEncoderLike | None = None,
    llm: LLMClient | None = None,
    sw_en: Translator | None = None,
    en_sw: Translator | None = None,
) -> Deps:
    """Production wiring (Ollama, MiniLM, cross-encoder, Marian, on-disk indexes); any component can be replaced."""

    def load() -> ContextPipeline:
        # Runtime is offline: models come from the local cache (scripts/setup_offline.py fills it once).
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        return load_pipeline(settings, embedder, reranker)

    return Deps(
        settings=settings,
        llm=llm or OllamaClient(settings),
        language=load_language_service(settings, sw_en, en_sw),
        refs=Router.from_settings(settings).refs,
        load_pipeline=load,
        load_laws=lambda: load_catalog(settings),
    )


def default_deps(settings: Settings) -> Deps:
    """Entry-point wiring with JSON logging: real components, or the synthetic fake stack when HAKI_FAKE_BACKENDS=1."""
    if settings.fake_backends:
        from backend.app.devstack import fake_deps  # dev-only; imports the test fakes

        deps = fake_deps(settings)
    else:
        deps = real_deps(settings)
    return dataclasses.replace(deps, setup_logging=True)


def warm_up(pipeline: ContextPipeline, language: LanguageService) -> None:
    """One tiny call through every lazy model (embedder, cross-encoder, both translators)."""
    pipeline.retrieve_context(WARMUP_EN)
    language.prepare_query(WARMUP_SW, "sw")
    language.translate_result(ParsedResponse(rights=WARMUP_EN))
