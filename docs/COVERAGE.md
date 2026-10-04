# Test coverage (v1.0, 2026-10-05)

Branch coverage of `backend/app` from the default test run (no models, no Ollama). The gate in `pyproject.toml` fails
below 85% overall. The M10 target is ≥ 85% for each of parsing (ingestion), retrieval, generation and lang, and all four
meet it.

| Package | Statements | Line coverage | Branches | Branch coverage | Combined |
|---|---|---|---|---|---|
| ingestion (parsing) | 600 | 97.2% | 128 | 93.8% | **96.6%** |
| retrieval | 636 | 98.6% | 82 | 93.9% | **98.1%** |
| generation | 392 | 99.7% | 74 | 97.3% | **99.4%** |
| lang | 266 | 96.2% | 52 | 100.0% | **96.9%** |
| evaluation | 929 | 97.4% | 194 | 94.3% | 96.9% |
| app root (API, sessions, security, offline, preflight, …) | 1070 | 97.1% | 170 | 92.9% | 96.5% |
| **Total** | 3893 | | 700 | | **97%** |

The main uncovered lines load real models or engines: `lang/translator.py` (MarianMT), `retrieval/reranker.py` and
`retrieval/embedder.py` (sentence-transformers) and `ingestion/extract.py` (Tesseract OCR). The `real`-marked tests
exercise them (`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 pytest -m real`; 5 passed, 1 skipped without pytesseract).

The frontend has 52 vitest tests and 2 Playwright end-to-end tests. Frontend coverage is not measured.

Regenerate: `./scripts/check.sh` prints the per-file table, and `pytest --cov --cov-report=json` gives the raw numbers.
