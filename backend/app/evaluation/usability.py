"""Usability survey analysis: SUS (Brooke 1996), paired before/after legal confidence, clarity and usefulness.

Input: eval/usability_responses.csv (copy eval/usability_responses.template.csv), one row per participant, every
answer on a 1-5 scale, entered by hand from eval/usability_survey.md. CLI: python eval/analyze_usability.py
"""

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import write_json
from backend.app.evaluation.metrics import describe, paired_bootstrap_ci

SUS_ITEMS = 10
LIKERT = range(1, 6)
SCALE_COLUMNS: tuple[str, ...] = (
    "confidence_before",
    "confidence_after",
    "clarity",
    "usefulness",
    *(f"sus_{i}" for i in range(1, SUS_ITEMS + 1)),
)
COLUMNS: tuple[str, ...] = ("participant", *SCALE_COLUMNS)


def sus_score(answers: Sequence[int]) -> float:
    """0-100 SUS score: odd items contribute (answer - 1), even items (5 - answer), sum x 2.5."""
    if len(answers) != SUS_ITEMS or any(a not in LIKERT for a in answers):
        raise ValueError("SUS needs 10 answers on a 1-5 scale")
    return 2.5 * sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))


def parse_responses(rows: Sequence[dict[str, str]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validated participant rows (ints) and one problem per missing or out-of-range value."""
    parsed, problems = [], []
    for line, row in enumerate(rows, start=2):
        values: dict[str, Any] = {"participant": (row.get("participant") or f"line {line}").strip()}
        for col in SCALE_COLUMNS:
            raw = (row.get(col) or "").strip()
            if not raw.isdigit() or int(raw) not in LIKERT:
                problems.append(f"line {line}: {col}={raw!r} is not 1-5")
            else:
                values[col] = int(raw)
        parsed.append(values)
    return (parsed if not problems else []), problems


def analyze(participants: Sequence[dict[str, Any]], *, resamples: int, seed: int) -> dict[str, Any]:
    """SUS per participant and summary, paired confidence change (with bootstrap CI), clarity and usefulness."""
    sus = [sus_score([p[f"sus_{i}"] for i in range(1, SUS_ITEMS + 1)]) for p in participants]
    before = [float(p["confidence_before"]) for p in participants]
    after = [float(p["confidence_after"]) for p in participants]
    changes = [a - b for a, b in zip(after, before, strict=True)]
    change: dict[str, Any] = {
        **describe(changes),
        "improved": sum(c > 0 for c in changes),
        "unchanged": sum(c == 0 for c in changes),
        "declined": sum(c < 0 for c in changes),
    }
    if participants:
        _, lo, hi = paired_bootstrap_ci(after, before, resamples=resamples, seed=seed)
        change["ci95"] = [lo, hi]
    return {
        "n": len(participants),
        "sus": describe(sus),
        "sus_by_participant": {p["participant"]: s for p, s in zip(participants, sus, strict=True)},
        "confidence_before": describe(before),
        "confidence_after": describe(after),
        "confidence_change": change,
        "clarity": describe([float(p["clarity"]) for p in participants]),
        "usefulness": describe([float(p["usefulness"]) for p in participants]),
    }


def _stat_row(name: str, stats: dict[str, Any]) -> str:
    """One markdown table row of descriptive statistics."""
    if not stats.get("n"):
        return f"| {name} | 0 | | | | |"
    return (
        f"| {name} | {stats['n']} | {stats['mean']:.2f} | {stats['sd']:.2f} | {stats['median']:.2f} | "
        f"{stats['min']:g}-{stats['max']:g} |"
    )


def render(result: dict[str, Any]) -> str:
    """Markdown table of the survey measures plus the paired change line."""
    lines = ["| Measure | n | Mean | SD | Median | Range |", "|---|---|---|---|---|---|"]
    for key in ("sus", "confidence_before", "confidence_after", "clarity", "usefulness"):
        lines.append(_stat_row(key, result[key]))
    change = result["confidence_change"]
    if change.get("n"):
        lo, hi = change["ci95"]
        lines.append(
            f"\nConfidence change (after - before): mean {change['mean']:+.2f} (95% bootstrap CI {lo:+.2f} to "
            f"{hi:+.2f}); improved {change['improved']}, unchanged {change['unchanged']}, declined {change['declined']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI. 0 on success, 1 when the responses file is missing or has invalid values."""
    parser = argparse.ArgumentParser(description="Analyse the usability survey responses.")
    parser.add_argument("path", nargs="?", type=Path, help="default: eval/usability_responses.csv")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    path = args.path or settings.usability_responses_path
    if not path.exists():
        print(f"{path} is missing; copy eval/usability_responses.template.csv and enter the answers", file=sys.stderr)
        return 1
    with path.open(newline="", encoding="utf-8") as fh:
        participants, problems = parse_responses(list(csv.DictReader(fh)))
    if problems:
        print("invalid responses:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    result = analyze(participants, resamples=settings.eval_bootstrap_resamples, seed=settings.eval_seed)
    write_json(settings.eval_results_dir / "usability.json", result)
    print(render(result), end="")
    return 0
