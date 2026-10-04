"""End-to-end functional run through the HTTP API (real stack on the laptop; TestClient over fakes in tests).

Per question: POST /api/query, read the SSE stream to its terminal event, GET /api/sources. Saves the answer, the
sources (verbatim, for raters), the citation report and timings to eval/results/functional.json.
Start the API first (`uvicorn backend.app.main:app`), then:
python eval/run_functional.py [--base-url URL] [--only ID ...]
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import read_json, write_json
from backend.app.models import CitationCheck, UserLanguage

TERMINAL_EVENTS = frozenset({"done", "error", "null"})
STREAM_TIMEOUT = httpx.Timeout(900.0, connect=5.0)
MAX_RATE_LIMIT_RETRIES = 3


class FunctionalQuery(BaseModel):
    """A question for the end-to-end run; expect_null marks the deliberately out-of-corpus ones."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    lang: UserLanguage
    category: str = Field(min_length=1)
    expect_null: bool = False


FUNCTIONAL_QUERIES = TypeAdapter(list[FunctionalQuery])


class SourceRecord(BaseModel):
    """One retrieved chunk as the Sources panel showed it."""

    chunk_id: str
    act: str
    unit_type: str
    section_num: str
    section_title: str
    page: int
    rank: int
    truncated: bool
    text: str


class FunctionalRecord(FunctionalQuery):
    """Everything the run observed for one question (error set when the API failed)."""

    null_response: bool = False
    acts: list[str] | None = None
    answer_en: str = ""
    sections_user: dict[str, str] | None = None
    citation_check: CitationCheck = Field(default_factory=CitationCheck)
    format_ok: bool = False
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = ""
    sources: list[SourceRecord] = Field(default_factory=list)
    tokens: int = 0
    query_s: float = 0.0
    ttft_s: float | None = None
    total_s: float = 0.0
    error: str | None = None


FUNCTIONAL_RECORDS = TypeAdapter(list[FunctionalRecord])


def read_events(lines: Iterable[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (event name, JSON data) from SSE lines; comments and keep-alives are skipped."""
    name = "message"
    for line in lines:
        if line.startswith("event:"):
            name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            yield name, json.loads(line.removeprefix("data:").strip())
            name = "message"


def _post_query(client: httpx.Client, query: FunctionalQuery, sleep: Callable[[float], None]) -> httpx.Response:
    """POST /api/query, waiting out 429 rate limits (Retry-After) a few times."""
    for _ in range(MAX_RATE_LIMIT_RETRIES):
        response = client.post("/api/query", json={"question": query.question, "language": query.lang})
        if response.status_code != 429:
            return response
        sleep(float(response.headers.get("retry-after", "60")))
    return response


def _error_code(response: httpx.Response) -> str:
    """'HTTP <status> <code>' from the API's uniform error body."""
    try:
        code = response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        code = "unknown"
    return f"HTTP {response.status_code} {code}"


def _consume_stream(client: httpx.Client, session_id: str, record: FunctionalRecord, start: float) -> None:
    """Fill the record from the SSE stream (tokens, translation, terminal event)."""
    parts: list[str] = []
    with client.stream("GET", f"/api/stream/{session_id}", timeout=STREAM_TIMEOUT) as response:
        if response.status_code != 200:
            response.read()
            record.error = _error_code(response)
            return
        for name, data in read_events(response.iter_lines()):
            if name == "token":
                if record.ttft_s is None:
                    record.ttft_s = time.perf_counter() - start
                parts.append(data["text"])
            elif name == "translated":
                record.sections_user = data["sections"]
            elif name in TERMINAL_EVENTS:
                _apply_terminal(record, name, data)
                break
    record.answer_en = "".join(parts)
    record.tokens = len(parts)


def _apply_terminal(record: FunctionalRecord, name: str, data: dict[str, Any]) -> None:
    """Copy the done/null/error payload into the record."""
    if name == "error":
        record.error = f"stream {data.get('code', 'error')}"
        return
    record.disclaimer = data.get("disclaimer", "")
    if name == "done":
        record.citation_check = CitationCheck.model_validate(data["citation_check"])
        record.format_ok = data["format_ok"]
        record.warnings = data["warnings"]


def run_query(
    client: httpx.Client, query: FunctionalQuery, sleep: Callable[[float], None] = time.sleep
) -> FunctionalRecord:
    """One question end to end; API failures are recorded in `error`, not raised."""
    record = FunctionalRecord(**query.model_dump())
    start = time.perf_counter()
    response = _post_query(client, query, sleep)
    record.query_s = time.perf_counter() - start
    if response.status_code != 200:
        record.error = _error_code(response)
        return record
    body = response.json()
    record.null_response, record.acts = body["null_response"], body["acts"]
    _consume_stream(client, body["session_id"], record, start)
    record.total_s = time.perf_counter() - start
    if not record.null_response and record.error is None:
        sources = client.get(f"/api/sources/{body['session_id']}").json()["chunks"]
        record.sources = [SourceRecord.model_validate(s) for s in sources]
    return record


def run_all(
    client: httpx.Client, queries: Sequence[FunctionalQuery], sleep: Callable[[float], None] = time.sleep
) -> list[FunctionalRecord]:
    """Run every query in order, printing one progress line each (ids and timings only)."""
    records = []
    for n, query in enumerate(queries, start=1):
        record = run_query(client, query, sleep)
        status = record.error or ("null" if record.null_response else f"{record.tokens} tokens")
        ttft = f"{record.ttft_s:.1f}" if record.ttft_s is not None else "-"
        print(f"[{n}/{len(queries)}] {query.id}: {status}, ttft {ttft} s, total {record.total_s:.1f} s")
        records.append(record)
    return records


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """CLI. 0 when every question got a response, 1 if any failed, 2 when the API is not healthy."""
    parser = argparse.ArgumentParser(description="Run the functional questions end to end through the API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--only", nargs="+", metavar="ID", help="run only these query ids")
    parser.add_argument("--out", type=Path, help="default: eval/results/functional.json")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    queries = FUNCTIONAL_QUERIES.validate_python(read_json(settings.functional_queries_path))
    if args.only:
        queries = [q for q in queries if q.id in set(args.only)]
    client = client or httpx.Client(base_url=args.base_url, timeout=60.0)
    with client:
        health = client.get("/api/health")
        if health.status_code != 200:
            print(f"API not healthy ({health.status_code}): {health.text[:300]}", file=sys.stderr)
            return 2
        records = run_all(client, queries, sleep)
    out = args.out or settings.eval_results_dir / "functional.json"
    write_json(out, [r.model_dump() for r in records])
    print(f"saved {out}")
    return 1 if any(r.error for r in records) else 0
