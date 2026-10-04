import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.config import ROOT_DIR, Settings
from backend.app.retrieval.bench import main, percentile, platform_info, summarize
from backend.app.retrieval.pipeline import ContextPipeline
from backend.tests.fake_pipeline import STORE, fake_pipeline


@pytest.mark.parametrize(
    ("p", "expected"),
    [(0.5, 3.0), (0.95, 5.0), (0.2, 1.0), (1.0, 5.0)],
)
def test_percentile_is_nearest_rank(p: float, expected: float) -> None:
    assert percentile([5.0, 1.0, 4.0, 2.0, 3.0], p) == expected


def test_percentile_of_nothing_is_an_error() -> None:
    with pytest.raises(ValueError, match="empty"):
        percentile([], 0.5)


def test_summarize_reports_p50_p95_per_stage() -> None:
    runs = [{"rerank": float(i), "total": 10.0 * i} for i in range(1, 21)]
    assert summarize(runs) == {"rerank": (10.0, 19.0), "total": (100.0, 190.0)}


def test_platform_info_has_cpu_and_ram() -> None:
    info = platform_info()
    assert {"python", "os", "cpu", "cores", "ram"} <= set(info)


@pytest.fixture(scope="module")
def pipe(tmp_path_factory: pytest.TempPathFactory) -> ContextPipeline:
    return fake_pipeline(tmp_path_factory.mktemp("sp"), Settings(relevance_threshold=1.0))


def test_bench_prints_stage_percentiles_and_platform(pipe: ContextPipeline, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-n", "7"], pipeline=pipe) == 0
    out = capsys.readouterr().out
    for stage in ("embed", "dense", "sparse", "rrf", "rerank", "total"):
        assert stage in out
    assert "p50" in out and "p95" in out and "cpu" in out and "runs: 7" in out


def test_bench_reads_queries_from_file(
    pipe: ContextPipeline, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    queries = tmp_path / "q.txt"
    queries.write_text("landlord evict tenant\n\nqxzv blorp\n", encoding="utf-8")
    assert main(["-n", "4", "--queries", str(queries)], pipeline=pipe) == 0
    assert "null: 2/4" in capsys.readouterr().out


def test_bench_without_indexes_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(chunks_path=tmp_path / "chunks.json", index_dir=tmp_path / "indexes")
    STORE.save(settings.chunks_path)
    assert main(["-n", "1"], settings=settings) == 2
    assert "build_index" in capsys.readouterr().err


def test_bench_script_runs_with_fakes() -> None:
    script = ROOT_DIR / "scripts" / "bench_retrieval.py"
    done = subprocess.run(
        [sys.executable, str(script), "--fake", "-n", "3"], capture_output=True, text=True, check=False, timeout=120
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert "rerank" in done.stdout and "runs: 3" in done.stdout
