"""HAKI_FAKE_BACKENDS=1: the API on the synthetic test corpus with fake models, no Ollama, no downloads.

For frontend development and API tests only. The corpus and answer are invented text from backend/tests (never statute
text); FakeReranker scores are shared-word counts, so the null threshold is 1 (at least one shared word).
"""

import tempfile
from pathlib import Path

from backend.app.config import DISCLAIMER, Settings
from backend.app.deps import Deps
from backend.app.interfaces import LLMClient, Translator
from backend.app.lang.service import load_language_service
from backend.app.retrieval.refs import RefExtractor

FAKE_THRESHOLD = 1.0
DEV_TOKEN_DELAY_S = 0.05
DEV_SCRIPT = (
    "## RIGHTS EXPLANATION\n",
    "An employer must prove a valid reason and a fair procedure ",
    "before ending your job (Sample Employment Act, s. 4).\n",
    "Wages are paid at the end of each month (Sample Employment Act, s. 6).\n\n",
    "## RECOMMENDED STEPS\n",
    "1. Write down the dates and what was said.\n",
    "2. Ask your employer in writing for the reason.\n\n",
    "## FORMAL LETTER\n",
    "[Date]\n\nDear [Recipient],\n\n",
    "I write to ask for the reason my employment ended and for my unpaid wages.\n\n",
    "Yours faithfully,\n[Your Name]\n\n",
    DISCLAIMER,
)


def fake_deps(
    settings: Settings,
    workdir: Path | None = None,
    *,
    llm: LLMClient | None = None,
    sw_en: Translator | None = None,
    en_sw: Translator | None = None,
) -> Deps:
    """Deps over the synthetic corpus (sparse index written under workdir, a temp dir by default)."""
    from backend.tests.fake_pipeline import ACTS, TABLE, fake_pipeline
    from backend.tests.fakes import FakeLLM, FakeTranslator

    fake_settings = settings.model_copy(update={"acts": ACTS, "relevance_threshold": FAKE_THRESHOLD})
    sparse_dir = (workdir or Path(tempfile.mkdtemp(prefix="hakiai-fake-"))) / "sparse"
    return Deps(
        settings=fake_settings,
        llm=llm or FakeLLM(list(DEV_SCRIPT), delay_s=DEV_TOKEN_DELAY_S),
        language=load_language_service(fake_settings, sw_en or FakeTranslator("en"), en_sw or FakeTranslator("sw")),
        refs=RefExtractor(ACTS, TABLE.aliases),
        load_pipeline=lambda: fake_pipeline(sparse_dir, fake_settings),
    )
