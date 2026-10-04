# HakiAI design (M0–M7) — read this instead of re-deriving
Precedence: this file wins on names/signatures. Deviations from ARCHITECTURE.md are logged in docs/DEVIATIONS.md.

## Tree  (backend/app/...; tests mirror in backend/tests/, fixtures in backend/tests/fixtures/)
config.py   Settings(pydantic-settings, env prefix HAKI_): paths, ACTS: list[ActSpec(name,year,file,url|None,unit:"Section"|"Article")],
            dense_k=20, sparse_k=20, rrf_k=60, top_n=20 (=RERANK_IN), rerank_top=5 (=RERANK_OUT), relevance_threshold
            (=RELEVANCE_MIN_SCORE), min_confident_chunks=2, models, ollama_url/model, temperature=0.1, num_ctx=8192,
            num_predict=1500, max_question_chars=1000, session_ttl_s, max_sessions=200, rate_limit_per_min=10, log_content=false,
            budgets (see sections below). Module constants FALLBACK_MESSAGE (§7.5 verbatim) and DISCLAIMER.
models.py   LegalChunk(chunk_id,act,act_slug,act_year,unit_type,chapter,part,section_num,section_title,text,page,repealed,source_sha256);
            RetrievedChunk(chunk,dense_rank,sparse_rank,rrf_score,rerank_score,truncated); SessionData(question,question_en,lang,
            chunks,fallback,acts,status:pending|running|done|aborted|error,answer_en,parsed,parsed_user,citation_check,
            untranslated,feedback_given); QueryRequest(question,language:"auto"|"en"|"sw");
            QueryResponse(session_id,null_response,acts,language); ParsedResponse(rights,steps,letter,format_ok);
            CitationCheck(verified,unmatched); SourceChunk/SourcesResponse; FeedbackIn(session_id,rating:"up"|"down",comment);
            FeedbackOut(recorded); ErrorBody(code,message)
interfaces.py  Protocols (runtime_checkable): Embedder(dim; encode; count_tokens), CrossEncoderLike(score),
            LLMClient(stream->AsyncGenerator[str,None]; async status->(reachable,model); async health), Translator(translate;
            translate_batch). Fakes in backend/tests/fakes.py: FakeEmbedder, FakeReranker, FakeLLM (DEFAULT_SCRIPT splits headers
            across tokens; model_present, pause_after/resume, fail_with, delay_s, records cancelled), FakeTranslator(tag, dictionary).
logging_setup.py configure_logging(settings, stream) → JSON lines; RedactContentFilter masks extra fields matching
            question|answer|text unless log_content; exceptions log exc_type only (no traceback text).
ingestion/  download.py ensure_pdfs(specs)->list[Path] (skip existing; raise MissingPDFError) | extract.py extract_pages(pdf)->list[tuple[int,str]]
            parse.py parse_act(pages,spec,sha256)->list[LegalChunk]; is_noise(line)->bool; is_repealed(text)->bool
            build_index.py main()  (chunks.json + indexes)
retrieval/  embedder.py STEmbedder (implements interfaces.Embedder: encode(list[str])->np.ndarray[n,384] L2-normalised; count_tokens) | windows.py make_windows(chunk,spec:WindowSpec)->list[str]
            dense.py DenseIndex.build(chunks,emb,*,spec,model_name,corpus_hash)/save(dir)/load(dir,*,model_name,corpus_hash)/search(vec,k,acts|None)->list[tuple[str,float]]
            sparse.py SparseIndex.build(chunks,dir,*,corpus_hash)/open(dir,*,corpus_hash)/search(q,k,acts|None[,refs in M3])->list[tuple[str,float]]; sanitize(q)->str
            meta.py IndexMeta, IndexMismatchError (stale/missing index → message with the rebuild command)
            store.py ChunkStore.save/load(path); get(ids)->list[LegalChunk]; all(); indexable() (non-repealed); corpus_hash
            router.py Router(table,refs).route(q)->list[str]|None (ordered; None = full corpus); domains.yaml; load_domains(path,acts)
            refs.py RefExtractor(acts,aliases).extract_refs(q)->list[Ref(unit,num,act|None)]; act_mentions(q)->list[slug]
            rrf.py rrf(*ranked:Sequence[str],k)->list[Fused(chunk_id,score,ranks)] (ties: best rank, then chunk_id)
            hybrid.py HybridRetriever(embedder,dense,sparse,store,router,settings).retrieve(q)->RetrievalResult(candidates:
            list[RetrievedChunk] top_n, acts, widened, timings_ms{route,embed,dense,sparse,rrf,total}, dense_only_ids, sparse_only_ids); retrieve_dense_only/
            retrieve_sparse_only (M9 baselines); load_retriever(settings, embedder|None); CLI prints candidates with ranks
            reranker.py CEReranker(model,max_length=512,batch=8; lazy shared model; warmup()) implements CrossEncoderLike (raw logits);
            pair_text(chunk) "{act} {unit} {num} {title}: {text}"; rerank(model,q,candidates,top)->list[RetrievedChunk] (desc, ties keep
            RRF order); is_confident(scored,threshold,min_chunks)->bool  (≥min_confident_chunks with score >= relevance_threshold, D13)
            pipeline.py ContextPipeline(retriever,reranker,settings).retrieve_context(q_en)->ContextResult(chunks ≤rerank_top, null,
            debug: ContextDebug(acts,widened,candidates,scores[(id,score)],timings_ms route/embed/dense/sparse/rrf/rerank/total));
            null → chunks=[]. load_pipeline(settings, embedder|None, reranker|None) | bench.py + scripts/bench_retrieval.py (p50/p95, --fake)
generation/ prompt.py build_prompt(q,chunks[,settings])->PromptBuild(system,user,chunks,chunk_flags[ChunkFlag(chunk_id,truncated,dropped)];
            .text "SYSTEM: …\n\nCONTEXT: …USER QUESTION: <question>…</question>", .truncated, .truncated_ids) (§7.1 + rules, D14)
            budget.py est_tokens(str,per_word)->int; truncate_text; fit_bodies([(header_tokens,body)],FitLimits)->list[Fitted(body|None,truncated)]
            llm.py OllamaClient(settings,transport|None) implements interfaces.LLMClient (POST /api/generate stream; aclose/cancel closes
            the response); OllamaError > OllamaUnavailable | ModelNotLoaded ("ollama pull …") | GenerationTimeout; status()->(reachable,model)
            parse.py SectionSplitter.feed(token)->list[SectionDelta(section,text)]; finalize()->ParsedResponse(+format_ok); split_sections(text)
            citations.py extract_citations(text,refs|None)->list[Citation(unit,num,act|None)]; check_citations(text,chunks,refs|None)->CitationCheck
            service.py generate_stream(prompt,llm,refs|None)-> TokenEvent(text,deltas)… then GenerationResult(full_text,sections,citation_check,truncated)
            gate.py LLMGate(max_queue).enter()->Ticket (GateFull); Ticket.positions() yields queue position until 0; release()
            (idempotent); active/waiting
lang/       detect.py detect_lang(text,min_chars,min_prob)/resolve_language(text,ui_lang,…)->"en"|"sw" (seeded) | segment.py segment(text,max_tokens,
            per_word,pack)->list[Part(text,translate)] | translator.py MarianTranslator(direction,settings) implements interfaces.Translator
            (lazy shared model; translate_batch); warmup(direction) | protect.py Protector(act_names,glossary|None).mask(text,style)->Masked;
            unmask(text,masked)->(str,lost:list); STYLES | glossary.py load_glossary(path)->Glossary(status,terms).lookup; render(sw,en)
            "mpangaji [tenant]" | service.py LanguageService.prepare_query(q,ui_lang)->PreparedQuery(english,original_lang,translated);
            translate_result(ParsedResponse)->TranslatedSections(sections_sw,untranslated_segments); load_language_service; load_ui_strings
            | glossary.json, ui_strings.json (both status needs_human_review)  (D15)
sessions.py SessionStore(ttl,max_sessions,clock).create(SessionData)->str/get(id)->SessionData|None/purge()->int (dict, absolute
            monotonic TTL; full → evict oldest done/aborted/error, then oldest pending; never running → SessionsFull)
letter.py   without_disclaimer(parsed); letter_text(parsed,disclaimer)->str; letter_docx(parsed,disclaimer)->bytes (footer)
security.py clean_question(q)->str; strip_invisible; clean_comment; RateLimiter(per_min,clock).allow(ip)->bool/retry_after/prune
feedback.py append_feedback(path,record) (fcntl.flock, JSONL)
deps.py     Deps(settings,llm,language,refs,load_pipeline,setup_logging); real_deps(settings,*,embedder,reranker,llm,sw_en,en_sw);
            default_deps(settings) (fake stack when settings.fake_backends) | devstack.py fake_deps(settings,workdir,*,llm,…)
stream.py   AnswerStream(settings,llm,language,refs,ui).run(id,session,ticket)/replay(session) → ServerSentEvents; error_info
web.py      BodyLimitMiddleware, SecurityHeadersMiddleware, SPAStaticFiles, error_response
main.py     create_app(deps, clock)->FastAPI; Runtime (sessions, gate, limiters, pipeline, models_warm) on app.state; module `app`
            = create_app(default_deps(get_settings())); routes: POST /api/query, GET /api/stream/{id} (SSE),
            GET /api/sources/{id}, GET /api/letter/{id}?format=txt|docx, GET /api/health, POST /api/feedback

## Chunks
- chunk_id = "{act_slug}-{section_num}" lowercased, Articles too (employment-act-41a, constitution-of-kenya-41); schedules
  "{act_slug}-sch{n}"; duplicates get "-2", "-3" in document order. Stable across rebuilds.
- unit_type: "section"|"article"|"schedule". chapter: CHAPTER heading or "" ; part: PART heading or "". page = start page.
- repealed=True when the body is only a repeal/deletion note ("[Repealed by ...]", "Deleted by ..."). Kept in chunks.json, excluded from both indexes.
- source_sha256 = sha256 of the source PDF; build_index rebuilds when any hash changes.

## Retrieval
- Embedding: all-MiniLM-L6-v2 truncates at 256 word-pieces. Chunks > embed_split_over_words (200) → windows of embed_window_words (180)
  starting every embed_window_stride (120) words, each prefixed "{act} — {unit} {num}: {title}. " (schedules: "{act} — {num}: {title}. ").
  Window vectors map back to parent chunk_id; chunk score = max over its windows. Text shown to users/LLM is always the full parent.
  build_index reports windows over embed_max_tokens (real corpus: 105/2274). See DEVIATIONS D12.
- FAISS: IndexFlatL2 over L2-normalised vectors (L2 order == cosine order); parallel array window_idx→chunk_id saved alongside.
  Domain filter via faiss IDSelectorBatch over the routed Acts' window ids; search all selected windows (flat index is exhaustive
  anyway), aggregate to unique chunk_ids. acts empty/None = full corpus.
  If filtered search yields < min_filtered_hits (5) chunks → rerun over the full corpus.
- Whoosh schema: chunk_id ID(stored,unique); act KEYWORD(lowercase); act_slug KEYWORD (filter); section_num ID (lowercase exact); section_title TEXT(StemmingAnalyzer, field_boost=2.0);
  text TEXT(StemmingAnalyzer). BM25F. Query = OR-group (0.9 coord bonus) over title+text+section_num; sanitize() keeps only word chars and
  lower-cases (so AND/OR/NOT are plain stopwords);
  extract_refs() adds boosted Term(section_num, n). Same Act filter + widen rule as FAISS.
- Router (domains.yaml): ≥25 Porter-stemmed terms/phrases per Act, Acts ordered by matched-term count then config order. The Constitution
  has its own rights terms and is appended as co-domain after employment/housing/police/CPC Acts. Explicit mentions override keywords:
  Act title/alias/"Cap N" → that Act; "Article N" → Constitution (named Acts first, in mention order). A bare "section N" names no
  Act, so keywords decide. No match → None (full corpus).
- Refs: "section N"/"s. N"/"sec N" bind to the nearest named Section-unit Act; bare ones resolve within the routed Acts. Each
  resolved, indexed chunk whose unit_type matches is put at sparse rank 1 (guarantees exact-reference hits reach the reranker).
- Widening: each leg (dense, sparse) with < min_filtered_hits (5) filtered hits is rerun unfiltered; widened = any leg widened.
- Reranker: cross-encoder outputs unbounded logits (not probabilities). relevance_threshold default 0.0, tuned in M9 on in-corpus vs
  out-of-corpus queries (eval/), result recorded in PROGRESS.md.

## Generation
- Ollama options: temperature 0.1, num_ctx 8192 (always sent explicitly), num_predict 1500.
- Prompt budget: settings.prompt_budget = num_ctx − num_predict − prompt_safety_tokens (256). Chunks are fitted in rank order: each gets
  min(own size, chunk_token_budget 1200, what is left); a shortened body is cut at a sentence/word boundary + "[... truncated — see Sources]";
  with < min_chunk_tokens (40) left the chunk is dropped (flagged truncated+dropped). est_tokens = ceil(1.4 × (words + punctuation marks)).
  Fixed parts alone over budget → PromptBudgetError. Truncated chunk_ids → `truncated: true` in /api/sources.
- Question: security.clean_question (control/format chars stripped, "[CHUNK"/role markers/<question>/[INST]/<s> neutralised, whitespace
  collapsed, capped at max_question_chars) and wrapped in <question> tags. The prompt asks the model to end with DISCLAIMER (D14).
- Concurrency: LLMGate = one generation at a time (CPU). Waiters FIFO, max_queue (8) else error code "busy" (503). Stream emits status
  events with queue position on every change. Client disconnect (request.is_disconnected) → cancel task → close httpx stream (stops Ollama)
  → release gate.
- Citation check: after generation, regex-extract (Act, Section/Article N) pairs from the English text; normalise ("s. 41(2)" → 41, Act
  aliases from config); verify against the chunks in the prompt
  (Act-bound: same act+unit+num; no Act named: any chunk with that unit+num). Schedules are not extracted. Unmatched → warnings in `done` event; UI shows a warning banner.

## SSE contract  (GET /api/stream/{id}; each event JSON; D16)
status {stage:"retrieved",chunks} → {stage:"queued",position} (on every change) → {stage:"generating"} | token {text, deltas:
[{section,text}]} | status {stage:"translating"} + translated {sections:{rights,steps,letter}} (sw only, before done) |
done {warnings:list[str] (user language), citation_check, format_ok, truncated_chunks:[ids], untranslated:[segments], disclaimer}
| error {code,message} | null {message (user language), disclaimer}. Keep-alive comment every sse_ping_s (15 s).
- Fallback sessions are created done and emit only `null` (every connection); the LLM is never called. The server accumulates
  answer_en, parsed (model disclaimer line removed) and parsed_user, so /api/letter and reconnects work after the stream.
- Generated once: pending → running (409 in_progress for other connections) → done (later connections replay: one token with
  the whole text, translated, done) | aborted (client left; 409) | error (409 generation_failed). Gate full → 503 busy.
- Disconnect: sse-starlette cancels the generator; generate_stream/llm.stream are closed with aclosing (closes the Ollama
  response); a background task after the response closes the run, releases the ticket and marks a still-running session aborted.
- Error codes: model_not_loaded, llm_unavailable, llm_timeout, llm_error, prompt_budget, internal.

## Language
- UI language is authoritative: "en"|"sw" used as given; "auto" → langdetect (DetectorFactory.seed=0; short input unreliable).
- sw: question sw→en before retrieval. English draft streams live as `token`; after done, each section is translated en→sw and sent as
  `translated`, which replaces the draft in the UI.
- Protection (D15): mask letter placeholders "[…]", Act names (+year), "Section/s./Article N(…)" lists, "Cap N", numbers and (en→sw only)
  glossary terms with "ZX{i}Q"; translate; unmask (glossary spans → "Kiswahili [English]"); a lost placeholder → retry with "#{i}";
  still lost → that sentence stays English and is listed in untranslated_segments (UI note). Questions: spans lost twice are appended.
- Answers are translated one sentence at a time, all sections in one translate_batch call. sw→en model is opus-mt-swc-en (sw-en absent).

## API / ops
- Feedback: POST /api/feedback {session_id, rating, comment≤max_comment_chars} → JSONL at data/feedback.jsonl, fcntl.flock, record =
  {timestamp, session_id, rating, comment (control chars stripped), language, null_response, chunk_ids}; once per session
  ({"recorded": false} after). Never question/answer/chunk text.
- Input: max_question_chars (1000) → 422; clean_question strips control chars and neutralises "[CHUNK", "SYSTEM:", "CONTEXT:", "USER QUESTION:".
- Rate limit: in-memory per-IP token bucket, rate_limit_per_min (10), separate buckets for /api/query and /api/feedback → 429 +
  Retry-After. Order on /api/query: validate → clean_question (empty → 422 empty_question) → rate limit → prepare → retrieve.
- Body limit max_body_bytes (16 KiB) → 413 body_too_large. Security headers on every response (CSP except /docs, /redoc);
  Cache-Control: no-store on /api/*. frontend/dist mounted at / after the API routes, unknown non-API paths → index.html.
- Sessions: TTL session_ttl_s (3600), max_sessions (200): purge expired, then evict oldest; never block.
- CORS: only cors_dev_origin (http://localhost:5173) and only when dev_mode=true; prod serves the static build same-origin.
- Errors: every non-2xx body = {"error": {"code": str, "message": str}} (exception handlers incl. validation).
- /api/health → {status:"ok"|"degraded", ollama, model_present, indexes_loaded, models_warm}; 200 if all true, else 503 with an
  added error {code:"degraded", message: the fixes}. Startup: load indexes (IndexMismatchError / StartupError with the rebuild
  and setup_offline commands), warm every model with one call, warn (not fail) if Ollama/model is missing, start the purge task.
- HAKI_FAKE_BACKENDS=1 (settings.fake_backends): devstack.py serves the synthetic test corpus with fake models (threshold 1.0,
  scripted answer with 50 ms/token) — frontend development only. `make api-fake` also sets HAKI_DEV_MODE for CORS.
- Privacy: logs carry ids, timings, counts, error codes only, unless log_content=true (default false).
- Disclaimer added by API/frontend on every response (incl. fallback), never by the LLM.

## Offline & tooling
- scripts/setup_offline.py (online, once): huggingface_hub snapshot_download of the 4 HF models + `ollama pull` of ollama_model.
- Runtime: main sets HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 before any model import.
- Tests: pytest-socket `--disable-socket --allow-unix-socket` in pyproject.toml (TestClient is in-process, needs no TCP);
  markers `real`/`slow` skipped by default (`-m "not real and not slow"`).
- scripts/check.sh = ruff check + ruff format --check + mypy (strict, backend incl. tests) + pytest --cov; fail_under 85 over
  backend/app ([tool.coverage] in pyproject.toml). CI workflow runs check.sh. Makefile wraps the common commands.

## Pins (co-resolved in the former uv.lock → mutually compatible; py3.11, torch from CPU index)
fastapi==0.142.2 uvicorn[standard]==0.54.0 pydantic==2.13.5 pydantic-settings==2.15.0 httpx==0.28.1 sse-starlette==3.5.0
pdfplumber==0.11.10 sentence-transformers==6.1.0 faiss-cpu==1.15.1 whoosh==2.7.4 torch==2.14.1 transformers==5.18.0
sentencepiece==0.2.2 sacremoses==0.2.0 langdetect==1.0.9 numpy==2.4.6 python-docx==1.2.0 | dev (backend/requirements-dev.txt):
pytest==9.1.1 pytest-cov==5.0.0 pytest-socket==0.8.1 coverage==7.16.2 ruff==0.16.10 mypy==1.20.2 PyYAML==6.0.3. No pytest-asyncio: 0.23 breaks on pytest 9; TestClient is sync.

## Ambiguities → defaults
- Constitution uses Chapters/Articles: CHAPTER → `chapter`, unit_type "article", ActSpec.unit="Article" used in citations.
- Prompt §7.1 lacks header instruction: append one fixed line naming the 3 headers; otherwise verbatim (plus truncation marker if needed).
- Fallback: QueryResponse.fallback=true, stream emits `null` with FALLBACK_MESSAGE, no LLM call.

## Carry-over (code not yet matching this file)
- none after M7.

## Needed from you
1. Install Ollama and `ollama pull mistral:7b-instruct-q4_K_M`. Needed only from M5 manual check / M7 health.
2. One-time internet for MiniLM, ms-marco cross-encoder, opus-mt-sw-en/en-sw (~1 GB) — tests never need them.
3. Act years + kenyalaw URLs (optional; PDFs already present). Years read from the PDFs in M1 for you to confirm.
4. Confirm old frontend/ scaffold (Vite+TS) may be replaced in M8; confirm .docx/.pdf/legacy stay git-ignored.
