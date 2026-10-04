# Progress log
(Claude updates this at the end of every milestone: done, decisions made, open issues, next step.)

- [x] M0 Scaffold — 2026-10-04 (redone to the amended DESIGN, same day)
- [ ] M1 … [ ] M10 not started

## M0 Scaffold (2026-10-04)
Done:
- Old untracked implementation (app/, scripts/, tests/, pyproject/uv.lock, old docs, copilot-instructions, old CI) moved to legacy/ (git-ignored, reference only).
- data/raw → data/raw_pdfs (10 PDFs present). backend/app/{config,models}.py; Protocol + Fake for Embedder, CrossEncoderLike, LLMClient, Translator.
- backend/requirements.txt, pytest.ini (pythonpath=.), scripts/ci.sh, .github/workflows/ci.yml. 18 tests green, no models/Ollama needed.
Decisions:
- Settings via pydantic-settings, env prefix HAKI_; ACTS tuple in config.py with ActSpec(name, year, file, url, unit).
- Dropped pytest-asyncio: 0.23.3 crashes collection under pytest 9.1 (FastAPI TestClient is sync, so not needed).
- python-docx and sacremoses not pinned yet: install hung (bandwidth shared with the Ollama pull); pin them in M7 / M6 when first used.
- Old frontend/ scaffold left untracked; M8 replaces it.
Open issues:
- Act years in config.py are from general knowledge (Employment 2007, L&T Shops 1965, Rent Restriction 1959, CPC 1930, Traffic 1953, Legal Aid 2016, ...): confirm against PDF cover pages in M1.
- README.md and LICENSE have uncommitted edits from before M0 (not touched; README still describes the old setup → rewrite in M10).
Next: M1 Ingestion.

## M0 Scaffold v2 — amended design (2026-10-04)
Done:
- pyproject.toml (ruff, mypy strict, pytest markers real/slow skipped by default, pytest-socket, coverage ≥85) replaces pytest.ini;
  scripts/check.sh replaces ci.sh; Makefile; CI runs check.sh; backend/requirements-dev.txt; data/README.md; docs/HUMAN_TODO.md.
- config.py: dense_k/sparse_k, num_ctx/num_predict, max_question_chars, max_sessions, rate_limit_per_min, log_content, validation
  (positive ints, http URL, rerank_top ≤ top_n, min_confident_chunks ≤ rerank_top, num_predict < num_ctx); FALLBACK_MESSAGE, DISCLAIMER.
- models.py: full LegalChunk (DESIGN fields, validated id/sha/page), RetrievedChunk, SessionData, CitationCheck, FeedbackIn, ErrorBody;
  QueryRequest enforces max_question_chars.
- interfaces.py (4 runtime_checkable Protocols, async LLMClient) + backend/tests/fakes.py; old per-module stubs removed.
- logging_setup.py: JSON lines, redaction of question/answer/text extras unless log_content, exceptions log type only.
- 45 tests green; ./scripts/check.sh passes (coverage 100%); actionlint clean on ci.yml.
Decisions:
- Names follow DESIGN.md (CrossEncoderLike, SessionData, top_n, rerank_top, relevance_threshold); the prompt's RetrievedChunk replaces
  ScoredChunk (rerank now returns RetrievedChunk). Prompt values win: num_predict 1500, max_sessions 200 → DEVIATIONS D10.
- No localhost socket allow-list: TestClient is in-process; only Unix sockets allowed (asyncio self-pipe).
- Coverage gate is 85% over all of backend/app (per-module include would fail while stage modules are empty).
- CLAUDE.md/README.md/LICENSE/prompts edits are the owner's uncommitted work; left out of this commit.
Open issues:
- Act years still unconfirmed (M1). embed_token_limit/embed_max_words remain until M2 replaces them with window settings.
Next: M1 Ingestion.
