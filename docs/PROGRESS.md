# Progress log
(Claude updates this at the end of every milestone: done, decisions made, open issues, next step.)

- [x] M0 Scaffold — 2026-10-04 (redone to the amended DESIGN, same day)
- [x] M1 Ingestion — 2026-10-04 (awaiting human review gate)
- [x] M2 Indexes — 2026-10-04
- [x] M3 Retrieval — 2026-10-04
- [x] M4 Rerank — 2026-10-04
- [x] M5 Generation — 2026-10-04
- [x] M6 Language — 2026-10-04
- [ ] M7 … [ ] M10 not started

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

## M3 Retrieval (2026-10-04)
Done:
- retrieval/: domains.yaml (10 Acts, 25–39 terms each, aliases, Kiswahili hints), router.py (Router, Porter-stemmed whole-word/phrase
  match, explicit override, Constitution co-domain), refs.py (RefExtractor: Act titles/aliases/Cap N, section/article refs),
  rrf.py (rrf with per-list ranks, deterministic ties), hybrid.py (HybridRetriever, 2-thread dense+sparse, widening, ref injection,
  dense-only/sparse-only baselines, load_retriever, CLI). config: min_filtered_hits=5, domains_path; validates top_n ≤ dense_k+sparse_k.
- 274 tests green (38 router questions), coverage 98%. Real smoke (5 queries) routes correctly; hybrid ~50 ms after model load.
Decisions:
- Router returns ordered list | None (milestone behaviour) instead of DESIGN's set; refs live in refs.py per the milestone; DESIGN.md updated.
- Widening is per leg: only the leg with < 5 filtered hits reruns unfiltered, so the other keeps its domain focus.
- Injected refs must exist in the store, be non-repealed and match the ref's unit (a bare "section 41" never pulls Article 41).
- Bare "section N" does not override keyword routing (it names no Act); it resolves within the routed Acts.
Open issues:
- Long schedules (e.g. Constitution Sch3) still score in BM25 for generic queries; M4's cross-encoder should demote them.
- "shop" routes refund questions to the Landlord & Tenant (Shops) Act too, which pulls in the Constitution co-domain; harmless, revisit in M9.
Next: M4 Rerank.

## M4 Rerank (2026-10-04)
Done:
- retrieval/reranker.py: CEReranker (ms-marco MiniLM, max_length 512, batch 8, Identity activation → raw logits, lazy model shared
  per process under a lock, warmup()), pair_text, rerank (stable on ties), is_confident (inclusive). config: reranker_max_length/batch_size.
- retrieval/pipeline.py: ContextPipeline.retrieve_context → ContextResult(chunks, null, debug ids/scores/timings); null → no chunks; load_pipeline.
  hybrid.py timings now split embed from dense and name the fusion stage "rrf".
- retrieval/bench.py + scripts/bench_retrieval.py (-n, --queries, --fake on the synthetic corpus). backend/tests/fake_pipeline.py shared by tests.
- 315 tests green, coverage 97.6%; real cross-encoder test passes. Real bench (Ryzen 7 PRO 5850U, 16 threads, 15 GiB, n=30):
  total p50 855 ms / p95 1033 ms; rerank p50 821 ms; embed 29 ms; sparse 20 ms; model load 7.8 s.
Decisions:
- DESIGN names kept over the milestone's (reranker.py/CEReranker, not rerank.py/CrossEncoderReranker); rerank() takes the model explicitly.
- Threshold inclusive per the milestone → DEVIATIONS D13. A confident result keeps all top-5 chunks, including ones below the threshold.
- pipeline.py imports no LLM code, so the null path cannot reach it; the endpoint-level spy test is M7's. warmup() is not on the
  CrossEncoderLike protocol (fakes need none); the bench warms up with one untimed query instead.
Open issues:
- Threshold 0.0 is too strict for lay phrasing: 4/10 bench questions go null (eviction 0.6/-1.5, land acquisition -2.7, legal aid -5.2,
  faulty-phone refund -8.5 with consumer-protection s.9 on top) while garbage/out-of-corpus score ≈ -10 to -11. M9 must tune it.
- The faulty-phone refund query ranks badly even before the threshold (top score -8.5): check retrieval recall for it in M9.
Next: M5 Generation.

## M5 Generation (2026-10-04)
Done:
- generation/: prompt.py (build_prompt → PromptBuild system/user/chunks/chunk_flags, §7.1 + rules, golden snapshot), budget.py
  (est_tokens, sentence/word truncation, rank-order fitting), llm.py (OllamaClient: /api/generate NDJSON stream, typed errors,
  cancellation closes the response, status/health via /api/tags), parse.py (incremental SectionSplitter + split_sections),
  citations.py (extract_citations with ranges/lists/subsections, Act aliases + Cap N via RefExtractor; check_citations),
  service.py (generate_stream → TokenEvent… GenerationResult). security.py clean_question (DESIGN's M7 module, needed now).
- config: ollama_connect/read/health timeouts (replace ollama_timeout_s), ollama_keep_alive, prompt_safety_tokens, chunk_token_budget,
  min_chunk_tokens, tokens_per_word; prompt_budget property; validators. RefExtractor exposes act_spans/names/article_act/section_acts.
- 414 tests green, coverage 98%; real Ollama test passes (mistral:7b-instruct-q4_K_M pulled and running).
Decisions:
- DESIGN names kept; milestone behaviour (prompt rules, words×1.4 estimate, marker text, service.py) → DEVIATIONS D14.
- Prompt sent as one §7.1-layout string (LLMClient protocol unchanged). format_ok = all three headers seen (order/duplicates allowed);
  headers with inline text after a colon ("Formal Letter: Dear …") are split. Unbound "section N" verifies against any given chunk.
- Fresh httpx.AsyncClient per call (no pool shared across event loops); read timeout 300 s covers CPU prompt evaluation.
- Estimate vs Ollama prompt_eval_count on real 5-chunk prompts: 2788 vs 2282 (employment ss.35/41/44/45 + Art 41) and 6396 vs 5207
  (five longest schedules/sections, all truncated, budget 6436): ~22% conservative, never under.
Open issues:
- The model ends with the DISCLAIMER line, which falls into the letter section: M7 letter export must strip it.
- Schedule citations ("Sixth Schedule") are not extracted or verified.
Next: M6 Language.

## M6 Language (2026-10-04)
Done:
- lang/: detect.py (resolve_language: UI choice authoritative; "auto" → seeded langdetect, < 20 chars or prob < 0.7 → "en"),
  segment.py (line → sentence → word pieces, list markers kept out, lossless join), translator.py (MarianTranslator: lazy shared
  model, offline-capable, beam 4, no sampling, batched; warmup(direction)), protect.py (Protector/unmask, two placeholder styles),
  glossary.py + glossary.json (86 terms, needs_human_review), service.py (LanguageService.prepare_query/translate_result,
  load_language_service, load_ui_strings) + ui_strings.json (EN/SW, needs_human_review). Translator protocol gains translate_batch.
- config: glossary_path, ui_strings_path, translate_max_tokens/batch_size/num_beams/max_new_tokens, lang_min_detect_chars/prob.
- 503 tests green, coverage 98%; real test (both Marian models, "Section 41" intact both ways) passes. sacremoses==0.2.0 pinned.
Decisions:
- opus-mt-sw-en is not on the Hub → opus-mt-swc-en (bnt-en tried: unusable) → DEVIATIONS D15, HUMAN_TODO.
- Placeholders measured on opus-mt-en-sw: ⟦i⟧/[i]/{i}/<i> are destroyed, ZX{i}Q and #{i} survive → used as primary/retry.
- Questions are masked too (swc-en turned "Section 41" into "41th century"); lost spans are appended to the English query.
- Answers go sentence by sentence in one batch (a lost placeholder costs one sentence, not a paragraph); letter placeholders and
  the closings "Yours faithfully/sincerely" are masked (the model hallucinated religious text for them). Sample 3-section
  answer: 6.2 s on CPU after warmup, 1 of 14 sentences left in English, all citations byte-identical.
- Mixed Sheng under "auto" detects as "en" (langdetect sees pt 0.57); the user's explicit EN/SW choice always wins.
Open issues:
- swc-en quality on Kenyan legal Swahili is weak ("mwenye nyumba … kodi" → "householder … tax"): M9 must measure retrieval on the
  5 Swahili functional queries; routing on the original Swahili via domains.yaml hints may be needed (M7/M9).
- en-sw output is uneven (glossary renders inside headings, e.g. "kusitishwa [TERMINATION]"); human review of glossary/UI strings pending.
- M7: emit untranslated_segments as a UI note (ui_strings untranslated_note) and show translation_note on every sw answer.
Next: M7 API.
