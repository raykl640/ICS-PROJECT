"""Automatic per-response checks on eval/results/functional.json; complements, not replaces, human grounding ratings.

Checks: null path correct (all), disclaimer present (all without an API error), and for answered questions: >= 1
citation, every citation verified against the retrieved chunks, three sections present, letter placeholders.
CLI: python eval/grounding_check.py
"""

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import write_json
from backend.app.evaluation.functional import FUNCTIONAL_RECORDS, FunctionalRecord
from backend.app.generation.parse import split_sections

CHECKS: tuple[str, ...] = (
    "null_path_correct",
    "disclaimer_present",
    "has_citation",
    "citations_verified",
    "sections_present",
    "letter_placeholders",
)
_PLACEHOLDER = re.compile(r"\[[^\[\]\n]{2,60}\]")


def check_record(record: FunctionalRecord) -> dict[str, bool | None]:
    """Each check's outcome for one response; None where it does not apply (null answers, API errors)."""
    results: dict[str, bool | None] = dict.fromkeys(CHECKS)
    results["null_path_correct"] = record.error is None and record.null_response == record.expect_null
    if record.error is not None:
        return results
    results["disclaimer_present"] = bool(record.disclaimer.strip())
    if record.null_response:
        return results
    sections = split_sections(record.answer_en)
    found = len(record.citation_check.verified) + len(record.citation_check.unmatched)
    results["has_citation"] = found >= 1
    results["citations_verified"] = found >= 1 and not record.citation_check.unmatched
    results["sections_present"] = all(s.strip() for s in (sections.rights, sections.steps, sections.letter))
    results["letter_placeholders"] = bool(_PLACEHOLDER.search(sections.letter))
    return results


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Per check: passed, applicable and pass rate."""
    out: dict[str, dict[str, float | int]] = {}
    for check in CHECKS:
        values = [row["checks"][check] for row in rows if row["checks"][check] is not None]
        passed = sum(values)
        out[check] = {"passed": passed, "applicable": len(values), "rate": passed / len(values) if values else 0.0}
    return out


def grounding_report(records: Sequence[FunctionalRecord]) -> dict[str, Any]:
    """Per-response checks plus the summary table data."""
    rows = [
        {"id": r.id, "lang": r.lang, "category": r.category, "error": r.error, "checks": check_record(r)}
        for r in records
    ]
    return {"n_responses": len(rows), "summary": summarize(rows), "per_response": rows}


def render(report: dict[str, Any]) -> str:
    """Markdown summary table and the ids failing each check."""
    lines = [f"Responses: {report['n_responses']}", "", "| Check | Passed | Applicable | Rate |", "|---|---|---|---|"]
    for check, s in report["summary"].items():
        lines.append(f"| {check} | {s['passed']} | {s['applicable']} | {s['rate']:.0%} |")
    failing = {
        check: [row["id"] for row in report["per_response"] if row["checks"][check] is False] for check in CHECKS
    }
    lines += ["", *(f"- {check} failed: {', '.join(ids)}" for check, ids in failing.items() if ids)]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI. 0 on success, 1 when functional.json is missing (run eval/run_functional.py first)."""
    parser = argparse.ArgumentParser(description="Automatic grounding checks on the functional run.")
    parser.add_argument("--functional", type=Path, help="default: eval/results/functional.json")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    path = args.functional or settings.eval_results_dir / "functional.json"
    if not path.exists():
        print(f"{path} is missing; run python eval/run_functional.py first", file=sys.stderr)
        return 1
    report = grounding_report(FUNCTIONAL_RECORDS.validate_json(path.read_bytes()))
    write_json(settings.eval_results_dir / "grounding.json", report)
    print(render(report), end="")
    return 0
