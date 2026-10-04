import numpy as np

from backend.app.generation.llm import FakeLLM, LLMClient
from backend.app.lang.translator import FakeTranslator, Translator
from backend.app.retrieval.embedder import Embedder, FakeEmbedder
from backend.app.retrieval.reranker import CrossEncoderLike, FakeReranker


def test_fake_embedder_shape_norm_and_determinism() -> None:
    emb: Embedder = FakeEmbedder()
    vecs = emb.encode(["unfair termination", "unfair termination", "rent increase"])
    assert vecs.shape == (3, 384)
    assert vecs.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vecs, axis=1), 1.0, rtol=1e-5)
    np.testing.assert_array_equal(vecs[0], vecs[1])


def test_fake_embedder_overlap_is_closer() -> None:
    a, b, c = FakeEmbedder().encode(["employer dismissal notice", "dismissal notice", "tenant rent"])
    assert float(a @ b) > float(a @ c)


def test_fake_embedder_empty_text_is_zero_vector() -> None:
    assert not FakeEmbedder().encode([""]).any()


def test_fake_reranker_scores_word_overlap() -> None:
    rr: CrossEncoderLike = FakeReranker()
    scores = rr.score("fired without notice", ["notice of termination", "traffic offences", "Fired without NOTICE."])
    assert scores[2] > scores[0] > scores[1]
    assert scores[1] <= 0.0


def test_fake_llm_streams_scripted_tokens_and_records_prompt() -> None:
    llm = FakeLLM(["## RIGHTS", " EXPLANATION"])
    client: LLMClient = llm
    assert "".join(client.stream("prompt text")) == "## RIGHTS EXPLANATION"
    assert llm.prompts == ["prompt text"]
    assert client.health()


def test_fake_translator_tags_text() -> None:
    tr: Translator = FakeTranslator("sw-en")
    assert tr.translate("haki yangu") == "[sw-en] haki yangu"
