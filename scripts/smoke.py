#!/usr/bin/env python
"""End-to-end smoke test of a running API: health -> one English query -> stream -> sources -> letter (.docx).

Start the API first (`uvicorn backend.app.main:app`), then: `python scripts/smoke.py [--base-url URL] [--question Q]`.
Prints time to first token and total time; exits 1 on any failure. Prints ids, timings and counts, not answer text.
"""

import argparse
import io
import json
import sys
import time
from typing import Any

import docx
import httpx

DEFAULT_QUESTION = "My employer dismissed me without notice. What are my rights?"
TERMINAL_EVENTS = {"done", "error", "null"}


class SmokeError(RuntimeError):
    """A smoke step failed."""


def check(condition: bool, message: str) -> None:
    """Raise SmokeError(message) unless condition holds."""
    if not condition:
        raise SmokeError(message)


def stream_events(client: httpx.Client, session_id: str) -> tuple[float | None, list[tuple[str, dict[str, Any]]]]:
    """Read the SSE stream until a terminal event; returns (seconds to first token, events)."""
    start = time.perf_counter()
    first_token: float | None = None
    events: list[tuple[str, dict[str, Any]]] = []
    name = "message"
    with client.stream("GET", f"/api/stream/{session_id}", timeout=httpx.Timeout(900, connect=5)) as response:
        check(response.status_code == 200, f"stream returned HTTP {response.status_code}")
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                events.append((name, json.loads(line.removeprefix("data:").strip())))
                if name == "token" and first_token is None:
                    first_token = time.perf_counter() - start
                if name in TERMINAL_EVENTS:
                    break
    return first_token, events


def run(base_url: str, question: str) -> None:
    """All smoke steps against base_url; raises SmokeError on the first failure."""
    with httpx.Client(base_url=base_url, timeout=60, headers={"X-Haki": "1"}) as client:
        health = client.get("/api/health")
        check(health.status_code == 200, f"health is {health.status_code}: {health.json().get('error')}")
        print("health      ok")

        start = time.perf_counter()
        query = client.post("/api/query", json={"question": question, "language": "en"})
        check(query.status_code == 200, f"query returned {query.status_code}: {query.text[:200]}")
        body = query.json()
        session_id = body["session_id"]
        print(f"query       {time.perf_counter() - start:.1f} s  session={session_id} acts={body['acts']}")
        check(not body["null_response"], "query got the null (fallback) response; try another --question")

        first_token, events = stream_events(client, session_id)
        total = time.perf_counter() - start
        name, final = events[-1] if events else ("none", {})
        check(name == "done", f"stream ended with {name}: {final}")
        tokens = sum(1 for event, _ in events if event == "token")
        check(first_token is not None, "no token was streamed")
        print(f"stream      first token {first_token:.1f} s, total {total:.1f} s, {tokens} tokens")
        print(f"            format_ok={final['format_ok']} citations={final['citation_check']}")

        sources = client.get(f"/api/sources/{session_id}").json()["chunks"]
        check(len(sources) > 0, "no sources returned")
        print(f"sources     {[s['chunk_id'] for s in sources]}")

        letter = client.get(f"/api/letter/{session_id}", params={"format": "docx"})
        check(letter.status_code == 200, f"letter returned {letter.status_code}: {letter.text[:200]}")
        paragraphs = docx.Document(io.BytesIO(letter.content)).paragraphs
        check(len(paragraphs) > 0, "letter .docx has no paragraphs")
        print(f"letter      .docx {len(letter.content)} bytes, {len(paragraphs)} paragraphs")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the smoke test; 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args(argv)
    try:
        run(args.base_url, args.question)
    except (SmokeError, httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"SMOKE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
