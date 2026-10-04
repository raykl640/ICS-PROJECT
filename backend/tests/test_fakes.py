import asyncio

import numpy as np

from backend.app.interfaces import CrossEncoderLike, Embedder, LLMClient, Translator
from backend.tests.fakes import FakeEmbedder, FakeLLM, FakeReranker, FakeTranslator


def _collect(llm: LLMClient, prompt: str) -> list[str]:
    async def run() -> list[str]:
        return [token async for token in llm.stream(prompt)]

    return asyncio.run(run())


def test_fakes_satisfy_their_protocols() -> None:
    embedder: Embedder = FakeEmbedder()
    reranker: CrossEncoderLike = FakeReranker()
    llm: LLMClient = FakeLLM()
    translator: Translator = FakeTranslator()
    assert isinstance(embedder, Embedder)
    assert isinstance(reranker, CrossEncoderLike)
    assert isinstance(llm, LLMClient)
    assert isinstance(translator, Translator)


def test_fake_embedder_shape_norm_and_determinism() -> None:
    vecs = FakeEmbedder().encode(["unfair termination", "unfair termination", "rent increase"])
    assert vecs.shape == (3, 384)
    assert vecs.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vecs, axis=1), 1.0, rtol=1e-5)
    np.testing.assert_array_equal(vecs[0], vecs[1])


def test_fake_embedder_overlap_is_closer() -> None:
    a, b, c = FakeEmbedder().encode(["employer dismissal notice", "dismissal notice", "tenant rent"])
    assert float(a @ b) > float(a @ c)


def test_fake_embedder_empty_text_is_zero_vector_and_counts_words() -> None:
    emb = FakeEmbedder()
    assert not emb.encode([""]).any()
    assert emb.encode([]).shape == (0, 384)
    assert emb.count_tokens("Section 41 (2) applies") == 4


def test_fake_reranker_scores_word_overlap() -> None:
    scores = FakeReranker().score("fired without notice", ["notice of termination", "traffic", "Fired without NOTICE."])
    assert scores[2] > scores[0] > scores[1]
    assert scores[1] <= 0.0


def test_fake_llm_default_script_splits_headers_across_tokens() -> None:
    llm = FakeLLM()
    tokens = _collect(llm, "prompt text")
    text = "".join(tokens)
    for header in ("## RIGHTS EXPLANATION", "## RECOMMENDED STEPS", "## FORMAL LETTER"):
        assert header in text
        assert header not in tokens
    assert llm.prompts == ["prompt text"]
    assert asyncio.run(llm.health())


def test_fake_llm_custom_script_and_unhealthy() -> None:
    llm = FakeLLM(["a", "b"], healthy=False)
    assert _collect(llm, "p") == ["a", "b"]
    assert not asyncio.run(llm.health())


def test_fake_translator_applies_dictionary_and_tag() -> None:
    tr = FakeTranslator(dictionary={"haki": "right", "kazi": "work"})
    assert tr.translate("Haki yangu kazi") == "[sw] right yangu work"
    assert FakeTranslator(tag="en").translate("hello") == "[en] hello"
