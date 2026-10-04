# Evaluation (M9)

Logic lives in `backend/app/evaluation/`; the scripts here are entry points. Results go to `eval/results/`,
and `python eval/report.py` assembles them into `eval/report.md`, skipping any step that has not been run.

| Step | Command | Needs |
|---|---|---|
| Answer key (human) | copy `ground_truth.template.json` to `ground_truth.json` and fill it in; then `python eval/validate_ground_truth.py` | chunks.json |
| Retrieval P@5 / Recall@20 / MRR | `python eval/run_retrieval.py` | ground truth, indexes, MiniLM, cross-encoder |
| Null threshold | `python eval/tune_threshold.py` (prints a value; config is never edited) | as above + `out_of_corpus.json` |
| Functional run | start the API, then `python eval/run_functional.py` (~2-3 min per answer on CPU) | Ollama, all models |
| Automatic grounding | `python eval/grounding_check.py` | `results/functional.json` |
| Rating sheets | `python eval/make_rating_sheet.py`; each rater fills `ratings/rater_N.csv` while reading `ratings/responses.md` | `results/functional.json` |
| Agreement | `python eval/agreement.py` (percent agreement, Fleiss' kappa) | at least two filled sheets |
| Usability | run `usability_survey.md` with participants, enter the answers in `usability_responses.csv` (copy the template), then `python eval/analyze_usability.py` | survey answers |
| Latency | `python eval/bench_latency.py -n 4` (first run cold) | Ollama, indexes |
| Everything offline | `python eval/run_eval.py` (validate, retrieval, threshold, grounding, agreement, usability, report, each only when its inputs exist) | |

## Ground truth format

```json
[{"id": "R01", "question": "...", "lang": "en", "category": "employment",
  "relevant": [{"act": "Employment Act", "section": "41"}, {"act": "Constitution of Kenya", "section": "41"}]}]
```

- `act`: the Act's title as in `data/sources.yaml` or its slug (`employment-act`).
- `section`: the section or Article number (`41`, `41A`, `Article 41`), or a schedule (`First Schedule`, `sch1`). If
  a number appears twice in one Act, the validator asks for the chunk id suffix (e.g. `5-2`).
- `lang`: `en` or `sw` (Kiswahili questions are translated with the API's sw→en model before retrieval).
- Repealed sections are rejected: they are not indexed, so retrieval can never return them.
- Run `python eval/schema.py` for the JSON Schema.

## Ratings

- `grounding`: 0 = claims not supported by the listed sources, 1 = partly supported, 2 = fully supported.
- `citations_correct`: `yes` if every cited section says what the answer claims, `no` otherwise, `na` if nothing is
  cited.
- Leave a cell empty to skip it; agreement uses only the items every rater filled.
