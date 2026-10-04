"""Feedback JSONL: append-only, one valid JSON object per line under concurrent writers."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.app.feedback import append_feedback


def test_append_creates_parent_and_writes_one_line_per_record(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "feedback.jsonl"
    append_feedback(path, {"session_id": "a", "comment": "Asante sana"})
    append_feedback(path, {"session_id": "b", "comment": ""})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["session_id"] for line in lines] == ["a", "b"]
    assert "Asante sana" in lines[0]


def test_concurrent_appends_do_not_interleave(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: append_feedback(path, {"session_id": str(i), "comment": "x" * 2000}), range(64)))
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert sorted(int(r["session_id"]) for r in records) == list(range(64))
