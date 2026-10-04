"""Human rating tooling: blank per-rater CSV sheets from the functional run, then inter-rater agreement.

Sheets (eval/ratings/rater_N.csv) have one row per answered question; raters read eval/ratings/responses.md (answer +
verbatim sources) and fill `grounding` (0 not supported, 1 partly, 2 fully supported by the sources),
`citations_correct` (yes / no / na when nothing is cited) and optional `comments`.
CLIs: python eval/make_rating_sheet.py [--force]; python eval/agreement.py
"""

import argparse
import csv
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.config import Settings, get_settings
from backend.app.evaluation.common import write_json
from backend.app.evaluation.functional import FUNCTIONAL_RECORDS, FunctionalRecord, SourceRecord
from backend.app.evaluation.metrics import fleiss_kappa, percent_agreement

COLUMNS: tuple[str, ...] = ("response_id", "lang", "category", "question", "grounding", "citations_correct", "comments")
SCALES: dict[str, tuple[str, ...]] = {"grounding": ("0", "1", "2"), "citations_correct": ("yes", "no", "na")}


def rateable(records: Sequence[FunctionalRecord]) -> list[FunctionalRecord]:
    """Answered questions without API errors (null responses have nothing to rate)."""
    return [r for r in records if r.error is None and not r.null_response]


def _source_label(source: SourceRecord) -> str:
    """'employment-act-41 — Employment Act section 41, Title (p. 23)'."""
    unit = f"{source.act} {source.unit_type} {source.section_num}"
    return f"{source.chunk_id} — {unit}, {source.section_title} (p. {source.page})"


def responses_markdown(records: Sequence[FunctionalRecord]) -> str:
    """Reading copy for raters: question, answer (and Kiswahili version), citation report and verbatim sources."""
    lines = ["# Responses to rate", "", "Rate each answer only against the sources listed under it.", ""]
    for r in records:
        lines += [f"## {r.id} ({r.lang}, {r.category})", "", f"**Question:** {r.question}", "", "### Answer", ""]
        lines += [r.answer_en.strip(), ""]
        if r.sections_user:
            lines += ["### Answer shown to the user (Kiswahili)", ""]
            lines += [text.strip() for text in r.sections_user.values() if text.strip()] + [""]
        check = r.citation_check
        lines += [
            f"**Citations matched to sources:** {', '.join(check.verified) or 'none'}",
            "",
            f"**Citations not found in sources:** {', '.join(check.unmatched) or 'none'}",
            "",
            "### Sources",
            "",
        ]
        for s in r.sources:
            lines += [f"**[{s.rank}] {_source_label(s)}**", "", s.text.strip(), ""]
    return "\n".join(lines)


def write_sheets(records: Sequence[FunctionalRecord], out_dir: Path, raters: int) -> list[Path]:
    """One blank CSV per rater plus responses.md; returns the sheet paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = rateable(records)
    (out_dir / "responses.md").write_text(responses_markdown(rows), encoding="utf-8")
    paths = []
    for n in range(1, raters + 1):
        path = out_dir / f"rater_{n}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(COLUMNS)
            writer.writerows([r.id, r.lang, r.category, r.question, "", "", ""] for r in rows)
        paths.append(path)
    return paths


@dataclass(frozen=True)
class Sheets:
    """Ratings per rater file: {response_id: {column: value}}, plus problems found while reading."""

    raters: dict[str, dict[str, dict[str, str]]]
    problems: list[str]


def read_sheets(paths: Sequence[Path]) -> Sheets:
    """Read rater CSVs, normalising values (lower-case, trimmed) and listing out-of-scale ones."""
    raters: dict[str, dict[str, dict[str, str]]] = {}
    problems = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        sheet = {}
        for line, row in enumerate(rows, start=2):
            values = {col: (row.get(col) or "").strip().lower() for col in SCALES}
            for col, value in values.items():
                if value and value not in SCALES[col]:
                    problems.append(f"{path.name} line {line}: {col}={value!r} not in {'/'.join(SCALES[col])}")
            sheet[row["response_id"]] = values
        raters[path.name] = sheet
    return Sheets(raters, problems)


def agreement_for(sheets: Sheets, column: str) -> dict[str, Any]:
    """Fleiss' kappa, percent agreement and the rating distribution for one column over items every rater filled."""
    scale = SCALES[column]
    names = list(sheets.raters)
    ids = sorted(set.intersection(*(set(s) for s in sheets.raters.values())))
    complete = [i for i in ids if all(sheets.raters[n][i][column] in scale for n in names)]
    counts = [[sum(sheets.raters[n][i][column] == c for n in names) for c in scale] for i in complete]
    out: dict[str, Any] = {"items": len(complete), "skipped": len(ids) - len(complete)}
    if not counts:
        return out | {"kappa": None, "unanimous": None, "pairwise": None, "distribution": {}}
    unanimous, pairwise = percent_agreement(counts)
    out |= {
        "kappa": fleiss_kappa(counts),
        "unanimous": unanimous,
        "pairwise": pairwise,
        "distribution": {c: sum(row[k] for row in counts) for k, c in enumerate(scale)},
    }
    if column == "grounding":
        out["mean_score"] = statistics.fmean(int(sheets.raters[n][i][column]) for i in complete for n in names)
    return out


def agreement_report(sheets: Sheets) -> dict[str, Any]:
    """Agreement for every rated column."""
    return {"raters": list(sheets.raters), **{col: agreement_for(sheets, col) for col in SCALES}}


def _fmt(value: float | None, pattern: str) -> str:
    """Format a statistic, or 'n/a' when undefined."""
    return "n/a" if value is None else format(value, pattern)


def render(report: dict[str, Any]) -> str:
    """Markdown table of agreement per column."""
    lines = [
        f"Raters: {len(report['raters'])}",
        "",
        "| Rating | Items | All agree | Pairwise agreement | Fleiss' kappa |",
        "|---|---|---|---|---|",
    ]
    for col in SCALES:
        a = report[col]
        lines.append(
            f"| {col} | {a['items']} | {_fmt(a['unanimous'], '.0%')} | {_fmt(a['pairwise'], '.0%')} | "
            f"{_fmt(a['kappa'], '.3f')} |"
        )
    if report["grounding"].get("mean_score") is not None:
        lines.append(f"\nMean grounding score (0-2): {report['grounding']['mean_score']:.2f}")
    return "\n".join(lines) + "\n"


def make_sheets_main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: write rater sheets; refuses to overwrite existing sheets (ratings may be in them) without --force."""
    parser = argparse.ArgumentParser(description="Create blank rating sheets from eval/results/functional.json.")
    parser.add_argument("--force", action="store_true", help="overwrite existing rater sheets")
    args = parser.parse_args(argv)
    settings = settings or get_settings()
    source = settings.eval_results_dir / "functional.json"
    if not source.exists():
        print(f"{source} is missing; run python eval/run_functional.py first", file=sys.stderr)
        return 1
    existing = sorted(settings.ratings_dir.glob("rater_*.csv"))
    if existing and not args.force:
        print(f"{len(existing)} rater sheet(s) already exist in {settings.ratings_dir}; use --force", file=sys.stderr)
        return 1
    paths = write_sheets(
        FUNCTIONAL_RECORDS.validate_json(source.read_bytes()), settings.ratings_dir, settings.eval_raters
    )
    print(f"wrote {len(paths)} sheets and responses.md to {settings.ratings_dir}")
    return 0


def agreement_main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: agreement over eval/ratings/rater_*.csv; 1 when fewer than two sheets or invalid values."""
    argparse.ArgumentParser(description="Inter-rater agreement (percent agreement, Fleiss' kappa).").parse_args(argv)
    settings = settings or get_settings()
    paths = sorted(settings.ratings_dir.glob("rater_*.csv"))
    if len(paths) < 2:
        print(f"need at least two rater sheets in {settings.ratings_dir}", file=sys.stderr)
        return 1
    sheets = read_sheets(paths)
    if sheets.problems:
        print("invalid ratings:", *sheets.problems, sep="\n  ", file=sys.stderr)
        return 1
    report = agreement_report(sheets)
    write_json(settings.eval_results_dir / "agreement.json", report)
    print(render(report), end="")
    return 0
