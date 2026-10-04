import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.ingestion.sample import format_chunk, load_chunks, main, select
from backend.app.models import LegalChunk


def make(slug: str, num: str, text: str = "Body text.") -> LegalChunk:
    return LegalChunk(
        chunk_id=f"{slug}-{num.lower()}",
        act=slug.replace("-", " ").title(),
        act_slug=slug,
        act_year=2000,
        unit_type="section",
        part="Part I - PRELIMINARY",
        section_num=num,
        section_title=f"Title {num}",
        text=text,
        page=int(num) if num.isdigit() else 1,
        source_sha256="0" * 64,
    )


CHUNKS = [make("a-act", str(n)) for n in range(1, 31)] + [make("b-act", str(n)) for n in range(1, 4)]


def test_sampling_is_reproducible_per_seed_and_in_document_order() -> None:
    first = select(CHUNKS, per_act=5, seed=7)
    assert first == select(CHUNKS, per_act=5, seed=7)
    assert first != select(CHUNKS, per_act=5, seed=8)
    a_nums = [int(c.section_num) for c in first if c.act_slug == "a-act"]
    assert len(a_nums) == 5 and a_nums == sorted(a_nums)
    assert [c.section_num for c in first if c.act_slug == "b-act"] == ["1", "2", "3"]


def test_filters_by_act_and_section() -> None:
    assert {c.act_slug for c in select(CHUNKS, per_act=50, act="b-act")} == {"b-act"}
    assert [c.chunk_id for c in select(CHUNKS, per_act=1, section="12")] == ["a-act-12"]
    assert [c.chunk_id for c in select(CHUNKS, per_act=1, act="b-act", section="2")] == ["b-act-2"]


def test_format_shows_ids_page_part_and_truncates() -> None:
    out = format_chunk(make("a-act", "4", "x" * 50), max_chars=10)
    assert "a-act-4" in out and "page 4" in out and "Part I - PRELIMINARY" in out
    assert "xxxxxxxxxx [... 40 more chars]" in out
    assert "x" * 50 in format_chunk(make("a-act", "4", "x" * 50), max_chars=0)


def test_main_prints_samples_from_chunks_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps([c.model_dump() for c in CHUNKS]))
    assert load_chunks(path) == CHUNKS
    assert main(["--per-act", "2", "--act", "b-act", "--seed", "1"], Settings(chunks_path=path)) == 0
    out = capsys.readouterr().out
    assert out.count("=== b-act-") == 2


def test_main_without_chunks_json_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([], Settings(chunks_path=tmp_path / "none.json")) == 2
    assert "build_corpus" in capsys.readouterr().err
