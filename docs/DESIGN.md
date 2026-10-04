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
            chunks,fallback,answer_en,parsed,parsed_user,done); QueryRequest(question,language:"auto"|"en"|"sw");
            QueryResponse(session_id,fallback:bool); ParsedResponse(rights,steps,letter); CitationCheck(verified,unmatched);
            FeedbackIn(session_id,rating:"up"|"down"); ErrorBody(code,message)
interfaces.py  Protocols (runtime_checkable): Embedder(dim; encode; count_tokens), CrossEncoderLike(score),
            LLMClient(stream->AsyncIterator[str]; async health), Translator(translate; translate_batch). Fakes in backend/tests/fakes.py:
            FakeEmbedder, FakeReranker, FakeLLM (DEFAULT_SCRIPT splits headers across tokens), FakeTranslator(tag="sw", dictionary).
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
            gate.py LLMGate (M7: concurrency 1, FIFO, positions)
lang/       detect.py detect_lang(text,min_chars,min_prob)/resolve_language(text,ui_lang,…)->"en"|"sw" (seeded) | segment.py segment(text,max_tokens,
            per_word,pack)->list[Part(text,translate)] | translator.py MarianTranslator(direction,settings) implements interfaces.Translator
            (lazy shared model; translate_batch); warmup(direction) | protect.py Protector(act_names,glossary|None).mask(text,style)->Masked;
            unmask(text,masked)->(str,lost:list); STYLES | glossary.py load_glossary(path)->Glossary(status,terms).lookup; render(sw,en)
            "mpangaji [tenant]" | service.py LanguageService.prepare_query(q,ui_lang)->PreparedQuery(english,original_lang,translated);
            translate_result(ParsedResponse)->TranslatedSections(sections_sw,untranslated_segments); load_language_service; load_ui_strings
            | glossary.json, ui_strings.json (both status needs_human_review)  (D15)
sessions.py SessionStore(ttl,max_sessions).create(SessionData)->str/get(id)->SessionData|None/update(...)  (dict + monotonic expiry)
letter.py   letter_text(parsed)->str; letter_docx(parsed)->bytes (python-docx)
security.py clean_question(q)->str; RateLimiter(per_min).allow(ip)->bool
feedback.py append_feedback(path,record) (fcntl.flock, JSONL)
main.py     create_app(deps: Deps)->FastAPI; Deps dataclass holds all interfaces (fakes injected in tests); routes:
            POST /api/query, GET /api/stream/{id} (SSE), GET /api/sources/{id}, GET /api/letter/{id}?fmt=txt|docx,
            GET /api/health, POST /api/feedback

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

## SSE contract  (GET /api/stream/{id}; each event JSON)
status {stage:"queued"|"generating"|"translating", position?:int} | token {text} | translated {rights,steps,letter} (sw only)
done {warnings:list[str], citation_check:CitationCheck, truncated:bool} | error {code,message} | null {message:FALLBACK_MESSAGE}
- Fallback sessions emit only `null` then close; the LLM is never called. Server accumulates the full text in the session
  (answer_en, parsed, parsed_user) so /api/letter and reconnects work after the stream; letter returns 409 until done.

## Language
- UI language is authoritative: "en"|"sw" used as given; "auto" → langdetect (DetectorFactory.seed=0; short input unreliable).
- sw: question sw→en before retrieval. English draft streams live as `token`; after done, each section is translated en→sw and sent as
  `translated`, which replaces the draft in the UI.
- Protection (D15): mask letter placeholders "[…]", Act names (+year), "Section/s./Article N(…)" lists, "Cap N", numbers and (en→sw only)
  glossary terms with "ZX{i}Q"; translate; unmask (glossary spans → "Kiswahili [English]"); a lost placeholder → retry with "#{i}";
  still lost → that sentence stays English and is listed in untranslated_segments (UI note). Questions: spans lost twice are appended.
- Answers are translated one sentence at a time, all sections in one translate_batch call. sw→en model is opus-mt-swc-en (sw-en absent).

## API / ops
- Feedback: POST /api/feedback {session_id, rating} → JSONL at data/feedback.jsonl, fcntl.flock, record = {ts, session_id, rating, lang,
  fallback, chunk_ids}. Never question/answer/chunk text.
- Input: max_question_chars (1000) → 422; clean_question strips control chars and neutralises "[CHUNK", "SYSTEM:", "CONTEXT:", "USER QUESTION:".
- Rate limit: in-memory per-IP token bucket, rate_limit_per_min (10) on /api/query and /api/feedback → 429.
- Sessions: TTL session_ttl_s (3600), max_sessions (200): purge expired, then evict oldest; never block.
- CORS: only cors_dev_origin (http://localhost:5173) and only when dev_mode=true; prod serves the static build same-origin.
- Errors: every non-2xx body = {"error": {"code": str, "message": str}} (exception handlers incl. validation).
- /api/health → {status:"ok"|"degraded", ollama:bool, model:bool, index:bool, models_loaded:bool}; 200 if ok else 503.
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
sentencepiece==0.2.2 sacremoses (pin M6) langdetect==1.0.9 numpy==2.4.6 python-docx (pin M7) | dev (backend/requirements-dev.txt):
pytest==9.1.1 pytest-cov==5.0.0 pytest-socket==0.8.1 coverage==7.16.2 ruff==0.16.10 mypy==1.20.2 PyYAML==6.0.3. No pytest-asyncio: 0.23 breaks on pytest 9; TestClient is sync.

## Ambiguities → defaults
- Constitution uses Chapters/Articles: CHAPTER → `chapter`, unit_type "article", ActSpec.unit="Article" used in citations.
- Prompt §7.1 lacks header instruction: append one fixed line naming the 3 headers; otherwise verbatim (plus truncation marker if needed).
- Fallback: QueryResponse.fallback=true, stream emits `null` with FALLBACK_MESSAGE, no LLM call.

## Carry-over (code not yet matching this file)
- M7: max_queue, CORS/dev_mode config; LLMGate; RateLimiter in security.py; setup_offline.py.

## Needed from you
1. Install Ollama and `ollama pull mistral:7b-instruct-q4_K_M`. Needed only from M5 manual check / M7 health.
2. One-time internet for MiniLM, ms-marco cross-encoder, opus-mt-sw-en/en-sw (~1 GB) — tests never need them.
3. Act years + kenyalaw URLs (optional; PDFs already present). Years read from the PDFs in M1 for you to confirm.
4. Confirm old frontend/ scaffold (Vite+TS) may be replaced in M8; confirm .docx/.pdf/legacy stay git-ignored.
