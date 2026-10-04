from backend.app.config import Settings
from backend.app.retrieval.windows import WindowSpec, chunk_header, make_windows
from backend.tests.corpus import CONSTITUTION, LONG_TAIL, LONG_TEXT, make_chunk

SPEC = WindowSpec(split_over=200, words=180, stride=120)


def test_header_format_per_unit_type() -> None:
    section = make_chunk("sample-tenancy-act", "3", "Eviction", "Body.")
    article = make_chunk(CONSTITUTION, "43", "Housing", "Body.", unit_type="article")
    schedule = make_chunk(CONSTITUTION, "First Schedule", "Counties", "Body.", unit_type="schedule")
    assert chunk_header(section) == "Sample Tenancy Act — Section 3: Eviction. "
    assert chunk_header(article) == "Sample Constitution — Article 43: Housing. "
    assert chunk_header(schedule) == "Sample Constitution — First Schedule: Counties. "


def test_short_chunk_is_one_window_with_whitespace_collapsed() -> None:
    chunk = make_chunk("sample-tenancy-act", "3", "Eviction", "A landlord\nshall  not evict.")
    assert make_windows(chunk, SPEC) == ["Sample Tenancy Act — Section 3: Eviction. A landlord shall not evict."]


def test_chunk_at_the_threshold_is_not_split() -> None:
    chunk = make_chunk("sample-tenancy-act", "3", "Eviction", " ".join(["word"] * 200))
    assert len(make_windows(chunk, SPEC)) == 1


def test_long_chunk_is_split_into_overlapping_header_prefixed_windows() -> None:
    words = [f"w{i}" for i in range(500)]
    chunk = make_chunk("sample-tenancy-act", "3", "Eviction", " ".join(words))
    windows = make_windows(chunk, SPEC)
    header = chunk_header(chunk)
    bodies = [w.removeprefix(header).split() for w in windows]
    assert all(w.startswith(header) for w in windows)
    assert [b[0] for b in bodies] == ["w0", "w120", "w240", "w360"]
    assert all(len(b) <= 180 for b in bodies)
    assert bodies[-1][-1] == "w499"
    assert set(bodies[0]) & set(bodies[1]) == {f"w{i}" for i in range(120, 180)}


def test_distinctive_tail_lands_only_in_the_last_window() -> None:
    windows = make_windows(make_chunk("sample-employment-act", "41", "Records", LONG_TEXT), SPEC)
    assert len(windows) > 1
    assert [LONG_TAIL in w for w in windows] == [False] * (len(windows) - 1) + [True]


def test_spec_from_settings() -> None:
    assert WindowSpec.from_settings(Settings()) == SPEC
