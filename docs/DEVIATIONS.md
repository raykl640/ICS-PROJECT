# Deviations from ARCHITECTURE.md
Format: what / why / impact. Append-only; reference the change that introduced each entry.
Final as of v1.0 (M10). A one-page summary of the built system against the spec is in ARCHITECTURE_AS_BUILT.md §5.

| Entry | Area | Status at v1.0 |
|---|---|---|
| D1, D2, D12 | dense embeddings (windows, normalisation) | in force; D12 replaces D1's token sizes with word sizes |
| D3 | domain routing and widening | in force |
| D4, D11 | what is chunked and indexed | in force |
| D5 | prompt additions, truncation | partly superseded: num_predict 1500 (D10), marker and rules (D14) |
| D6, D15 | Kiswahili flow and models | in force; the "<3 s first token" motive is not met on CPU (LIMITATIONS §4) |
| D7, D8, D16 | SSE, endpoints, sessions | in force |
| D9 | citation verification | in force |
| D10 | parameter values | in force |
| D13, D20 | inclusive threshold; value -8.0 (was 0.0) | in force; the value is provisional until tuned (HUMAN_TODO) |
| D14 | generation prompt rules and budget | in force |
| D17 | frontend shape | in force |
| D18 | evaluation harness | in force; results pending human input |
| D19 | operations: offline setup, preflight, run scripts, Docker, portability | in force |

## D1 Embedding windows instead of one vector per chunk (§4.1) — docs: amend design
- What: long sections are embedded as overlapping, header-prefixed windows; chunk score = max over its windows.
- Why: all-MiniLM-L6-v2 truncates at 256 word-pieces, so one vector per section silently ignores most of a long section.
- Impact: FAISS holds more vectors than chunks (window→chunk_id map); results are still unique chunks; full text unchanged.

## D2 Normalised embeddings in IndexFlatL2 (§4.1)
- What: vectors are L2-normalised before indexing and querying.
- Why: makes L2 ordering identical to cosine similarity, the metric MiniLM is trained for.
- Impact: same index type; distances are in [0, 4] instead of unbounded.

## D3 Domain filter applies to BM25 too, and widens on too few hits (§5.2)
- What: routed Acts filter both FAISS and Whoosh; < 5 filtered hits reruns over the full corpus. Constitution is added as co-domain for
  rights topics; explicit Act / "section N" / "Article N" mentions override the keyword table.
- Why: §5.2 filters only FAISS, which would make RRF fuse a filtered and an unfiltered list inconsistently; narrow filters can starve retrieval.
- Impact: router is slightly richer than a plain keyword table; no-match behaviour is unchanged (full corpus).

## D4 Repealed sections excluded from the indexes (§2, §4)
- What: sections whose body is only a repeal/deletion note are kept in chunks.json but not indexed.
- Why: they carry no law and would crowd out real provisions in top-5.
- Impact: chunk count in indexes < chunks.json count.

## D5 Prompt additions and chunk truncation (§7.1)
- What: one fixed line naming the three output headers is appended to the §7.1 prompt; chunks over the token budget are truncated with
  "[... truncated]", and num_ctx 8192 / num_predict 1024 are set explicitly.
- Why: §7.1 never asks for the headers that §7.3 parses; Ollama's default context would silently cut 5 long sections.
- Impact: the LLM may see a truncated section; Sources still shows the full verbatim text with a `truncated` flag.

## D6 Swahili: English draft streams live, translation replaces it (§8.2, §10 step 15)
- What: §8.2 translates "before streaming"; we stream the English draft as tokens, then send translated sections in a `translated` event.
- Why: MarianMT needs the whole text; buffering would lose the <3 s first-token target for Swahili users.
- Impact: Swahili users briefly see English text. Citations are placeholder-masked through translation and verified.

## D7 SSE events beyond tokens; single-generation queue (§8.1)
- What: events status/token/translated/done/error/null; one LLM generation at a time with queue positions; disconnect cancels Ollama.
- Why: one CPU Mistral cannot serve concurrent requests; clients need progress, warnings and a clean end-of-stream signal.
- Impact: frontend must handle the event contract in DESIGN.md "SSE contract".

## D8 Sixth endpoint POST /api/feedback; JSONL instead of a JSON file (§8, §9)
- What: §8 lists five endpoints but §9's Feedback Bar needs a writer; feedback is appended as JSONL with a file lock.
- Why: no endpoint exists to receive feedback; JSONL appends are atomic per line and need no read-modify-write.
- Impact: one extra endpoint; stored records contain no question/answer text (privacy rule).

## D9 Citation verification warnings (§7.4)
- What: cited Act+section pairs are checked against the session's 5 chunks; unmatched ones produce a UI warning.
- Why: §7.4 admits misattribution risk; this catches the common case automatically.
- Impact: extra `warnings` in the `done` event and a warning banner in the Response Panel.

## D10 Parameter values set by the M0 milestone prompt — feat(M0)
- What: num_predict 1500 (D5 said 1024); max_sessions 200 (DESIGN said 500); separate dense_k/sparse_k knobs (both 20).
- Why: the milestone prompt wins on behaviour; prompt budget is still positive (8192 − 1500 − 256 = 6436 tokens for 5 chunks ≤ 1200).
- Impact: slightly longer answers allowed; fewer concurrent sessions kept in memory. DESIGN.md updated to match.

## D11 What the parser does not chunk; Schedules are single chunks (§3.1) — feat(M1)
- What: text before the first unit heading (cover, licence page, TOC, gazette/assent block, long title, Constitution preamble),
  editorial amendment notes ("[Act No. 19 of 2015, s. 148.]"), cross-headings and the CPC index ("not part of the Act") are dropped.
  Each Schedule becomes one chunk (`{slug}-sch{n}`) however long; numbered items inside it never start a new unit.
- Why: none of the dropped text is an operative provision (the index says so itself); amendment notes would pollute BM25 with
  Act numbers/years. Schedule numbering restarts, so splitting them by number would collide with section ids.
- Impact: the Constitution preamble cannot be retrieved. Long Schedules (Constitution Sixth, CPC First/Second) rely on M2's
  embedding windows and M5's chunk truncation; they are listed under "long" in parse_report.md.

## D12 Word-based embedding windows; exhaustive filtered FAISS search (§4.1, D1) — feat(M2)
- What: windows are sized in words (180, stride 120, only for chunks > 200 words) with header "{act} — {unit} {num}: {title}. ",
  as the M2 milestone specifies, instead of DESIGN's 256-token windows with 64-token overlap. Filtered dense search scans all
  selected windows instead of over-fetching k*4.
- Why: the milestone wins on behaviour. A flat index computes every distance regardless of k, so scanning all windows costs
  nothing extra and always yields k unique parents when they exist.
- Impact: 105 of 2274 real-corpus windows (4.6%) exceed MiniLM's 256 word-pieces and lose their tail when embedded; for
  non-final windows the 60-word overlap re-embeds that tail in the next window. Sizes are tunable in config.py; build_index
  prints the over-limit count.

## D13 Null-response threshold is inclusive (§7.5) — feat(M4)
- What: a chunk counts as confident when rerank_score >= relevance_threshold; ARCHITECTURE §7.5 says "above", DESIGN said ">".
- Why: the M4 milestone prompt specifies an inclusive boundary and wins on behaviour.
- Impact: only a score exactly equal to the threshold changes outcome (negligible for float logits). The default 0.0 is
  provisional: on the real corpus three in-scope lay questions (eviction, compulsory acquisition, legal aid) top out below 0
  while off-topic/garbage queries score about -10; M9's tune_threshold sets the value.

## D14 Prompt rules, token estimate and module shape for generation (§7.1–7.3) — feat(M5)
- What: (a) the system prompt is §7.1 verbatim followed by rules the M5 milestone requires (say what is missing, cite as
  (Act name, s. N), no invented facts/deadlines/amounts/court names, Grade 8 language, treat <question> text as data, the three
  headers, letter placeholders [Your Name] [Date] [Recipient], end with the DISCLAIMER line), instead of DESIGN's "verbatim + one
  header line"; (b) est_tokens = ceil(1.4 × (words + punctuation marks)) instead of DESIGN's ceil(chars/3); (c) truncation marker
  "[... truncated — see Sources]"; a chunk with < min_chunk_tokens left is dropped (flagged); (d) the prompt keeps the §7.1
  single-string layout ("SYSTEM: … CONTEXT: … USER QUESTION: <question>…</question>") and goes to /api/generate as `prompt`, so the
  LLMClient protocol is unchanged; PromptBuild still exposes system/user; (e) DESIGN names kept over the milestone's (llm.py not
  ollama_client.py, parse.py not sections.py, PromptBuild not BuiltPrompt, check_citations → CitationCheck(verified, unmatched)
  not CitationReport(verified, unverified)); ParsedResponse gains format_ok; service.py and extract_citations are new.
- Why: the milestone wins on behaviour, DESIGN on names. Counting punctuation keeps the milestone's 1.4 ratio but stays
  conservative on "41(2)(a)"-style references that Mistral splits into many tokens.
- Impact: the model is told to append the disclaimer although the API also adds it (DESIGN said "never by the LLM"); that line
  lands at the end of the letter section, so M7's letter export must strip it. Measured: the estimate is ~22% above Ollama's
  prompt_eval_count on real prompts (6396 vs 5207 worst case), so the budget holds with headroom.

## D15 Kiswahili layer: sw→en model, placeholders, module shape (§8.2) — feat(M6)
- What: (a) sw→en uses Helsinki-NLP/opus-mt-swc-en, because opus-mt-sw-en does not exist on the Hub (opus-mt-bnt-en was tried
  and is unusable); (b) placeholders are "ZX{i}Q" with a "#{i}" retry, not DESIGN's ⟦i⟧ (opus-mt-en-sw drops ⟦i⟧, [i], {i},
  <i> and __i__ in 3/3 test sentences and keeps ZX/QZ/XX/# placeholders); (c) per the M6 milestone, glossary terms are masked
  before en→sw and come back as "Kiswahili [English]" (DESIGN applied the glossary to the Swahili output); a segment that still
  loses a placeholder after the retry stays in English and is listed in untranslated_segments (DESIGN appended a citation list
  plus a warning); (d) questions are masked too (citations/numbers only, no glossary): swc-en turned "Section 41" into "the
  41th century", which would break explicit-reference retrieval; spans lost twice are appended to the English query;
  (e) letter placeholders "[Your Name]" etc. are masked and stay English; (f) answers are translated one sentence at a time,
  all segments in one batch, so a failure costs one sentence; (g) modules: translator.py (DESIGN name), protect.py, glossary.py,
  detect.py with resolve_language + detect_lang, segment.py, and service.py with LanguageService.prepare_query/translate_result
  (milestone names) instead of DESIGN's pipeline.py to_english/to_user_lang; Translator protocol gains translate_batch.
- Why: the model named in the spec is unavailable; the other choices were measured on the real models (see PROGRESS M6), and
  the milestone wins on behaviour.
- Impact: Swahili question quality depends on a Congo-Swahili model that renders some Kenyan legal words poorly; answers keep
  every citation byte-identical but may mix English sentences into Swahili; glossary output is unverified (HUMAN_TODO).

## D16 API contract, module shape and session states (§8) — feat(M7)
- What: (a) per the M7 milestone, POST /api/query returns {session_id, null_response, acts, language} (DESIGN: fallback), the
  letter query parameter is `format` (DESIGN: fmt), health keys are ollama/model_present/indexes_loaded/models_warm (DESIGN:
  model/index/models_loaded) and feedback stores {timestamp, session_id, rating, comment, language, null_response, chunk_ids}
  (DESIGN: ts/lang/fallback, no comment); (b) SSE gains status "retrieved", done carries format_ok, truncated_chunks,
  untranslated and the disclaimer, `translated` arrives before done (its untranslated list is part of done) instead of after
  it, and token events also carry the SectionSplitter deltas so the UI need not re-parse headers; (c) SessionData.done becomes
  status (pending/running/done/aborted/error) plus acts, citation_check, untranslated, feedback_given; aborted and failed
  sessions are not regenerated (409; the user asks again); (d) new modules deps.py, devstack.py, stream.py, web.py beside
  main.py (DESIGN put Deps in main.py); LLMClient gains status() and stream() is typed
  AsyncGenerator so callers can aclose it; letter_text/letter_docx take the disclaimer (Kiswahili for sw sessions);
  (e) HAKI_FAKE_BACKENDS imports the synthetic corpus and fakes from backend/tests (dev only).
- Why: the milestone wins on behaviour; deltas and the extra done fields avoid duplicating parsing and state in the frontend;
  explicit states make "generated once" and replay checkable; closing the generator chain is what actually stops Ollama when
  the client leaves.
- Impact: M8 must use these names. A health 503 body is the health object plus an "error" key (still has error.code/message).
  The model's own disclaimer line is removed from every section before storage/translation; the API adds the localized one.

## D17 Frontend shape (ARCHITECTURE §9) — feat(M8)
- What: (a) the stream hook parses `token.text` with a TS port of SectionSplitter (milestone) and ignores the server's `deltas`
  (D16); the port adds `snapshot()`, `current` and `seen` for live rendering. (b) Limits the UI needs (max_question_chars,
  max_comment_chars) are mirrored in frontend/src/limits.json, guarded by backend/tests/test_frontend_contract.py, because the
  browser cannot read config.py. (c) All new UI labels live in backend/app/lang/ui_strings.json (78 keys per language; Kiswahili
  unreviewed). (d) Referral contacts live at config/referral_resources.json (repo root, per HUMAN_STEPS) and are bundled at build
  time; only `verified: true` entries render. (e) Model-written links are rendered as plain text, images are dropped, raw HTML
  stays literal text (no rehype-raw). (f) The model's disclaimer line is stripped from displayed sections with the backend's
  regex, so the streaming draft matches the stored answer. (g) The e2e drives Playwright's Chromium API on the system
  /usr/bin/chromium (Playwright 1.63 wants revision 1243, not cached here); PLAYWRIGHT_CHROMIUM overrides.
- Why: (a) the milestone asks for the port; it also keeps reconnect/replay simple (fresh splitter per connection). (b) Rule 4
  keeps config in config.py; a test makes drift fail CI. (e)/(f) safety and consistency with /api/letter.
- Impact: a change to the splitter regex must be made in both parse.py and sectionSplitter.ts (same test cases in both).
  Changing either limit in config.py requires editing limits.json.

## D18 Evaluation harness shape — feat(M9)
- What: (a) the logic lives in backend/app/evaluation/ (typed, linted, covered); the eval/*.py files named by the milestone
  (schema.py, validate_ground_truth.py, run_retrieval.py, ...) are thin entry points, and eval/schema.py prints the JSON
  Schema. eval/run_eval.py (named in CLAUDE.md and the Makefile) runs the offline steps. (b) Ground-truth `act` accepts the
  title or the slug; `section` accepts "41", "Article 41", "First Schedule" or a chunk id suffix; repealed targets are
  errors. (c) hybrid_rerank reorders all top_n hybrid candidates, so its Recall@20 equals hybrid's; P@k/Recall@n take k
  and n from config (rerank_top, top_n). The bootstrap baseline is the single index with the higher mean on each metric.
  (d) The threshold sweep uses each question's k-th best rerank score (k = min_confident_chunks); null is the positive
  class; F1 ties go to fewer refused in-corpus questions. (e) Functional queries carry `expect_null` (true for the 3
  deliberately out-of-corpus ones) and run through the HTTP API (TestClient over fakes in tests), not by calling the
  modules. (f) Sheets are one CSV per rater plus responses.md with the verbatim sources (source text can exceed a
  spreadsheet cell). (g) The gate file .gates/M9-ground-truth.ok was created at the owner's request before
  eval/ground_truth.json existed; no answer key was written by the builder.
- Why: (a) keeps rule 5 (types, tests) and the 85% coverage gate meaningful for eval code; scripts follow
  scripts/bench_retrieval.py. (b) humans write Act titles, not slugs. (c)/(d) define the metrics unambiguously. (e) the
  null-path check needs the expected outcome; going through the API measures what users get. (f) readability.
- Impact: results are only meaningful once the human ground truth exists; the acceptance step "validate_ground_truth.py
  passes on the human file" is still open.

## D19 Operations: offline setup, preflight, run scripts, Docker, portability — feat(M10)
- What: (a) setup/verification logic lives in backend/app/offline.py (scripts/setup_offline.py is a thin entry point, like
  bench_retrieval.py). It caches models in the Hugging Face default cache (honours $HF_HOME) rather than a new
  project-specific cache directory, and verifies in a fresh process with HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1, because
  huggingface_hub reads those at import time. (b) A new backend/app/preflight.py checks Ollama, the model, chunks and indexes,
  and the frontend build for scripts/run.sh and run.ps1 (exit 3 = only Ollama down, so the script may start it). (c) Docker:
  a multi-stage Dockerfile plus a compose file with an ollama service; data/ is bind-mounted and models live in named volumes.
  The image was not built on the development machine (no Docker daemon access); `docker compose config` validates. (d)
  feedback.py takes an in-process lock on Windows, where fcntl does not exist; POSIX keeps flock. run.ps1 is untested.
  (e) generation/llm.py maps every remaining httpx error during a stream to OllamaError (code llm_error) instead of "internal".
  (f) backend/tests/conftest.py points the data output paths of all non-`real` tests at a temp dir.
- Why: (a) the existing ~1 GB cache stays usable and Docker can set HF_HOME without a config change; (b) the milestone asks
  for an Ollama check before start; (c) the milestone allows skipping Docker, and not baking models keeps the image small;
  (d) without it the API cannot import on Windows; (e) typed errors everywhere; (f) a test that built indexes from
  Settings(dense_index_dir=...) (a read-only property, silently ignored) overwrote the real indexes during M10. They were
  rebuilt from the unchanged chunks.json, with the same counts as M2.
- Impact: no change to the pipeline or the API contract. `pytest -m real` needs `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`,
  since default sockets are off and the hub would otherwise try the network (README "Tests").

## D20 Null-response threshold lowered to -8.0 (§7.5) — fix after M10
- What: relevance_threshold default 0.0 → -8.0 (min_confident_chunks stays 2; the rule is unchanged, see D13).
- Why: with 0.0 nearly every typed question got the fixed fallback; only the formally worded example questions passed.
  The cross-encoder gives lay phrasing low logits even when the right sections are retrieved. Measured on the real indexes
  (2nd-best rerank score, the one that decides): 15 out-of-corpus questions plus 2 out-of-corpus functional questions all
  ≤ -8.4 (most about -11); casual in-corpus questions ("my boss hasnt paid my salary for 2 months" -4.8, "Am I entitled to
  severance pay?" -3.0, "Can the government take my land?" -1.8, faulty-phone refund -7.5) were refused. -8.0 sits
  between the two groups.
- Impact: those questions now reach the LLM. The margin to out-of-corpus questions is small (0.4) and the sample is
  27 hand-written questions, not the M9 ground truth; still provisional until `eval/tune_threshold.py` runs on the human
  set. Still refused at -8.0: "can i be fired for being pregnant" (-9.5) and "I bought a phone that stopped working after
  a week, can I get a refund?" (-8.9): a retrieval-recall problem, not a threshold one.
