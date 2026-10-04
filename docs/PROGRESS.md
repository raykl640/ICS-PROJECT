# Progress log
(Claude updates this at the end of every milestone: done, decisions made, open issues, next step.)

- [x] M0 Scaffold — 2026-10-04 (redone to the amended DESIGN, same day)
- [x] M1 Ingestion — 2026-10-04 (awaiting human review gate)
- [x] M2 Indexes — 2026-10-04
- [ ] M3 … [ ] M10 not started

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

## M1 Ingestion (2026-10-04)
Done:
- data/sources.yaml (10 Acts, FRBR URIs from the PDFs, url: null) is now the Act list loaded by config.py (slug checked on load).
- ingestion/: download.py (verify/download, never overwrite, retries, sha256 → data/corpus_manifest.json), extract.py (pdfplumber,
  density check, optional OCR behind OcrEngine + FakeOcrEngine), profiles.py (ParserProfile; default + Constitution), parse.py,
  report.py, build_corpus.py, sample.py + scripts/inspect_chunks.py. docs/PARSING_NOTES.md written before the parser.
- Real corpus: 1519 chunks (Constitution 264 Articles + 6 Schedules); 0 gaps/duplicates/out-of-order/mid-sentence; 133 repealed.
- 121 tests green (synthetic reportlab PDFs, no real statute text), coverage 97%; ./scripts/check.sh passes.
Decisions:
- Act years confirmed against FRBR URIs (all config years were right). 10 Acts per BUILD_PLAN (milestone text says 9).
- Headings accepted only in ascending order within heading_max_gap (10): rejects TOC remnants, footnotes, numbered lists.
- Line-end hyphens are real compounds in this corpus → joined, hyphen kept. Em dash kept; other dashes → "-".
- A unit whose heading is a repeal note is repealed=True even with an orphan body line (CPC s.185 in the official PDF).
- Each Schedule = one chunk; preamble, amendment notes, cross-headings and the CPC index dropped → DEVIATIONS D11.
- requests + PyYAML runtime pins; reportlab, types-requests, types-PyYAML dev pins; pytesseract stays an unpinned optional extra.
Open issues:
- build_corpus takes ~4 min (pdfplumber over ~740 pages); fine for a one-off build.
- Long chunks for M2 windows: Constitution Sch6 (3761 words), CPC Sch1 offence table (7889, interleaved columns), CPC Sch2,
  Land s.2, Consumer s.2, Rent s.14.
Blocked: human review gate — see docs/HUMAN_TODO.md (inspect_chunks --per-act 20, then touch .gates/M1-reviewed.ok).
Next: M2 Indexes, only after .gates/M1-reviewed.ok exists.

## M2 Indexes (2026-10-04)
Done:
- retrieval/: store.py (ChunkStore, canonical corpus_hash), windows.py, embedder.py (STEmbedder, local_files_only under HF_HUB_OFFLINE),
  dense.py (IndexFlatL2 + window id map, IDSelectorBatch act filter, best window per parent), sparse.py (Whoosh BM25F, sanitize),
  meta.py (meta.json, IndexMismatchError with rebuild command). ingestion/build_index.py CLI; build_corpus now writes via ChunkStore.
- Real corpus: 1519 chunks, 1386 indexed (133 repealed skipped), 2274 windows; dense 3.4 MB / 49 s, sparse 2.5 MB / 4 s (MiniLM now cached).
- 189 tests green, coverage 97.7%; real MiniLM test passes ("wrongful dismissal" → unfair-termination chunk in top 5).
Decisions:
- DESIGN names kept over the milestone's (ChunkStore.get not get_many; STEmbedder in embedder.py; search(..., acts) by act_slug, not
  allowed_chunk_ids). Empty/None acts = full corpus in both indexes. Index dirs are owned and wiped on rebuild (settings.dense/sparse_index_dir).
- Word windows per milestone, exhaustive filtered dense search → DEVIATIONS D12. config: embed_token_limit/embed_max_words replaced by
  embed_split_over_words/window_words/window_stride/max_tokens/batch_size.
- sanitize() keeps only word chars and lower-cases (no Whoosh syntax can survive); section_num is a query field so "section 8" hits s.8.
Open issues:
- For "section 41 termination" BM25 ranks s.42/s.45 (which cite "section 41") above s.41: M3's extract_refs boost must fix this.
- 105/2274 windows exceed 256 word-pieces (see D12); revisit window size if M9 retrieval eval shows misses on long sections.
Next: M3 Retrieval.

