"""Run every offline evaluation step whose inputs exist, then assemble the report.

Retrieval and threshold need the human ground truth (validated first); grounding, agreement and usability run when
their input files exist. The functional run and the latency benchmark need Ollama and take minutes per question,
so they are started by hand (eval/run_functional.py, eval/bench_latency.py). CLI: python eval/run_eval.py
"""

import argparse
from collections.abc import Sequence

from backend.app.config import Settings, get_settings
from backend.app.evaluation import grounding, rating, report, retrieval_eval, schema, threshold, usability


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    """CLI: 0 when every step that ran succeeded, else 1 (the report is written either way)."""
    argparse.ArgumentParser(description="Run the offline evaluation steps and write eval/report.md.").parse_args(argv)
    settings = settings or get_settings()
    codes: dict[str, int] = {}
    if settings.ground_truth_path.exists():
        codes["validate"] = schema.validate_main([], settings)
        if codes["validate"] == 0:
            codes["retrieval"] = retrieval_eval.main([], settings)
            codes["threshold"] = threshold.main([], settings)
    else:
        print(f"skip retrieval/threshold: {settings.ground_truth_path} not written yet (human task)")
    if (settings.eval_results_dir / "functional.json").exists():
        codes["grounding"] = grounding.main([], settings)
    if len(list(settings.ratings_dir.glob("rater_*.csv"))) >= 2:
        codes["agreement"] = rating.agreement_main([], settings)
    if settings.usability_responses_path.exists():
        codes["usability"] = usability.main([], settings)
    codes["report"] = report.main([], settings)
    failed = [step for step, code in codes.items() if code != 0]
    print(f"steps run: {', '.join(codes)}; failed: {', '.join(failed) or 'none'}")
    return 1 if failed else 0
