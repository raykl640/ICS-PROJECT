# Changelog

All notable changes to HakiAI. Dates are 2026. Each milestone is one commit; details and measurements are in
[docs/PROGRESS.md](docs/PROGRESS.md), and every departure from the specification is in [docs/DEVIATIONS.md](docs/DEVIATIONS.md).

## [1.0.0] — unreleased

Build complete (M0–M10). The `v1.0.0` tag is applied only after the final audit (`prompts/FINAL_AUDIT.md`) finds no
critical issue.

### M10 Hardening, offline packaging, documentation (10-05)
- **Offline setup:** `scripts/setup_offline.py` (logic in `backend/app/offline.py`) caches the four Hugging Face models,
  pulls the Ollama model, builds chunks and indexes, and verifies everything loads in a fresh process with
  `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`.
- **Run scripts:** `scripts/run.sh` and `run.ps1` build the UI if needed, run `backend.app.preflight` (Ollama, model,
  indexes, build; Ollama is started if installed), then serve the API and UI on one port.
- **Robustness:** every remaining httpx error during generation now maps to the typed `llm_error`. New tests cover:
  - Ollama dying mid-stream (error event, session failed, gate released, next answer works);
  - a 50-user mixed load with no leaked sessions, tasks or file descriptors;
  - fuzzed questions (Unicode, control characters, lone surrogates, prompt-injection strings);
  - hostile request bodies;
  - path traversal on the static route;
  - hardening headers on every kind of response;
  - no content in logs on error paths.
- **Safety:**
  - Default tests can no longer write into `data/` (`backend/tests/conftest.py`).
  - Windows-safe feedback lock.
  - Dependency audit clean (`pip-audit`, `npm audit`).
  - Licence inventory in `docs/LICENSES.md`.
- **Docker (optional):** multi-stage `Dockerfile` and `docker-compose.yml` with an `ollama` service. Models and data are
  mounted, not baked in. Not built on the development machine.
- **CI:** a frontend job (lint, typecheck, vitest, build).
- **Docs:**
  - new: `docs/USER_GUIDE.md`, `ARCHITECTURE_AS_BUILT.md` (Mermaid), `LIMITATIONS.md`, `TRACEABILITY.md`, `COVERAGE.md`;
  - rewritten: `README.md`;
  - finalised: `DEVIATIONS.md` (D19);
  - `scripts/check_links.py` checks every relative link, with a test.
- **Verified:** `pytest -m real` passes with the offline variables (5 passed, 1 skipped).

### M9 Evaluation harness (10-05)
- `backend/app/evaluation/` + `eval/` entry points: ground-truth schema and validator; P@5, Recall@20, MRR for FAISS vs BM25 vs
  hybrid vs hybrid+rerank with paired bootstrap CIs; null-threshold sweep; functional runner over the HTTP API; grounding
  checks; rater sheets with Fleiss' κ; SUS analysis; latency bench; report. Results await human ground truth and raters.

### M8 Frontend (10-05)
- React 19 + Vite + Tailwind 4: Query panel, streamed Response tabs (Rights / Steps / Letter), verbatim Sources panel with
  citation jump, letter copy/.txt/.docx, feedback bar, null-response screen, health banner, EN/SW UI; served by FastAPI.

### M7 API (10-04)
- FastAPI with POST /api/query, SSE /api/stream, /api/sources, /api/letter (txt/docx), /api/feedback, /api/health;
  sessions with TTL, one-at-a-time LLM gate with a FIFO queue, rate limits, body limit, security headers, fake-backend mode.

### M6 Language (10-04)
- Kiswahili: seeded detection, MarianMT translators (opus-mt-swc-en, opus-mt-en-sw), citation/number/placeholder masking,
  glossary rendered as "Kiswahili [English]", sentence-wise answer translation.

### M5 Generation (10-04)
- §7.1 prompt with rules and a token budget, Ollama streaming client with typed errors, incremental section splitter,
  citation extraction and verification against the retrieved chunks.

### M4 Rerank (10-04)
- ms-marco cross-encoder reranking top-20 → top-5, inclusive threshold, null-response decision, retrieval benchmark.

### M3 Retrieval (10-04)
- Keyword domain router (domains.yaml), Act/section/Article reference extraction, RRF (k=60), parallel hybrid retriever
  with per-leg widening.

### M2 Indexes (10-04)
- Chunk store with corpus hash, header-prefixed embedding windows, FAISS IndexFlatL2 over MiniLM, Whoosh BM25F, stale-index
  detection.

### M1 Ingestion (10-04)
- PDF verification and download, pdfplumber extraction with optional OCR, per-Act parser profiles, parse report: 1519
  chunks from 10 Acts.

### M0 Scaffold (10-04)
- Layout, settings, models, interfaces with fakes, JSON logging with content redaction, ruff/mypy/pytest gate, CI.
