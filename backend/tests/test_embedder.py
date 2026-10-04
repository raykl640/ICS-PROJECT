import sys
import types
from typing import Any, ClassVar

import numpy as np
import pytest

from backend.app.interfaces import Embedder
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.embedder import STEmbedder
from backend.app.retrieval.store import ChunkStore
from backend.app.retrieval.windows import WindowSpec
from backend.tests.corpus import EMPLOYMENT, corpus


class _RecordingModel:
    """Stands in for sentence_transformers.SentenceTransformer; records constructor and encode arguments."""

    instances: ClassVar[list["_RecordingModel"]] = []

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.encode_kwargs: dict[str, Any] = {}
        self.tokenizer = lambda text, **_: {"input_ids": [0, *range(len(text.split())), 0]}
        _RecordingModel.instances.append(self)

    def get_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray[Any, np.dtype[np.float64]]:
        self.encode_kwargs = kwargs
        return np.ones((len(texts), 4), dtype=np.float64) / 2


@pytest.fixture
def fake_st(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingModel]:
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _RecordingModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    _RecordingModel.instances.clear()
    return _RecordingModel


@pytest.mark.parametrize(("env", "offline"), [(None, False), ("1", True), ("0", False), ("true", True)])
def test_local_files_only_follows_hf_hub_offline(
    fake_st: type[_RecordingModel], monkeypatch: pytest.MonkeyPatch, env: str | None, offline: bool
) -> None:
    if env is None:
        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    else:
        monkeypatch.setenv("HF_HUB_OFFLINE", env)
    STEmbedder("some/model", batch_size=8)
    model = fake_st.instances[-1]
    assert model.name == "some/model"
    assert model.kwargs == {"device": "cpu", "local_files_only": offline}


def test_encode_normalises_batches_and_returns_float32(fake_st: type[_RecordingModel]) -> None:
    emb = STEmbedder("some/model", batch_size=8)
    assert isinstance(emb, Embedder)
    vectors = emb.encode(["a b", "c"])
    assert vectors.dtype == np.float32
    assert vectors.shape == (2, emb.dim) == (2, 4)
    kwargs = fake_st.instances[-1].encode_kwargs
    assert kwargs["normalize_embeddings"] is True
    assert kwargs["batch_size"] == 8


def test_count_tokens_includes_special_tokens(fake_st: type[_RecordingModel]) -> None:
    assert STEmbedder("some/model", batch_size=8).count_tokens("three word text") == 5


@pytest.mark.real
def test_real_minilm_finds_unfair_termination_for_wrongful_dismissal() -> None:
    store = ChunkStore(corpus())
    emb = STEmbedder("sentence-transformers/all-MiniLM-L6-v2", batch_size=32)
    spec = WindowSpec(split_over=200, words=180, stride=120)
    index = DenseIndex.build(store.indexable(), emb, spec=spec, model_name="minilm", corpus_hash=store.corpus_hash)
    hits = index.search(emb.encode(["wrongful dismissal"])[0], k=5)
    assert f"{EMPLOYMENT}-4" in [cid for cid, _ in hits]
