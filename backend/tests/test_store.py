import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.retrieval.store import ChunkStore
from backend.tests.corpus import corpus, make_chunk


def test_save_load_roundtrip_keeps_order_and_hash(tmp_path: Path) -> None:
    store = ChunkStore(corpus())
    path = tmp_path / "chunks.json"
    store.save(path)
    loaded = ChunkStore.load(path)
    assert loaded.all() == store.all()
    assert loaded.corpus_hash == store.corpus_hash
    assert len(loaded) == 22


def test_get_returns_chunks_in_requested_order_and_rejects_unknown_ids() -> None:
    store = ChunkStore(corpus())
    got = store.get(["sample-tenancy-act-3", "sample-employment-act-4"])
    assert [c.section_title for c in got] == ["Eviction", "Unfair termination"]
    with pytest.raises(KeyError):
        store.get(["no-such-chunk"])
    assert "sample-tenancy-act-3" in store
    assert "no-such-chunk" not in store


def test_indexable_excludes_repealed_but_store_keeps_them() -> None:
    store = ChunkStore(corpus())
    assert len(store.indexable()) == 20
    assert not any(c.repealed for c in store.indexable())
    assert store.get(["sample-employment-act-7"])[0].repealed


def test_corpus_hash_ignores_file_formatting_but_tracks_content(tmp_path: Path) -> None:
    chunks = corpus()
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps([c.model_dump() for c in chunks]), encoding="utf-8")
    assert ChunkStore.load(path).corpus_hash == ChunkStore(chunks).corpus_hash
    edited = [*chunks[:-1], chunks[-1].model_copy(update={"text": "Changed."})]
    assert ChunkStore(edited).corpus_hash != ChunkStore(chunks).corpus_hash


def test_duplicate_chunk_ids_are_rejected() -> None:
    chunk = make_chunk("sample-tenancy-act", "2", "Rent", "Text.")
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        ChunkStore([chunk, chunk])


def test_load_validates_every_chunk(tmp_path: Path) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps([{"chunk_id": "Bad Id"}]), encoding="utf-8")
    with pytest.raises(ValidationError):
        ChunkStore.load(path)
