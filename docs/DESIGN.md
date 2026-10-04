# HakiAI design (M0–M7) — read this instead of re-deriving
## Tree  (backend/app/...; tests mirror in backend/tests/, fixtures in backend/tests/fixtures/)
config.py   Settings(pydantic-settings): paths, ACTS: list[ActSpec(name,year,file,url|None,unit:"Section"|"Article")],
            RRF_K=60, TOP_N=20, RERANK_TOP=5, THRESHOLD=0.0, MIN_CHUNKS=2, models, OLLAMA_URL/MODEL, TEMP=0.1, SESSION_TTL=3600
models.py   LegalChunk(chunk_id,act,part,section_num,section_title,text,page,act_year); ScoredChunk(chunk,score);
            QueryRequest(question,language:"auto"|"en"|"sw"); QueryResponse(session_id,fallback:bool); ParsedResponse(rights,steps,letter)
ingestion/  download.py ensure_pdfs(specs)->list[Path] (skip existing; raise MissingPDFError) | extract.py extract_pages(pdf)->list[tuple[int,str]]
            parse.py parse_act(pages,spec)->list[LegalChunk]; is_noise(line)->bool | build_index.py main()  (chunks.json + indexes)
retrieval/  embedder.py Embedder(Protocol).encode(list[str])->np.ndarray[n,384]; STEmbedder; FakeEmbedder (hash→unit vec)
            dense.py DenseIndex.build(chunks,emb)/save(dir)/load(dir)/search(vec,k,acts|None)->list[tuple[str,float]]
            sparse.py SparseIndex.build(chunks,dir)/open(dir)/search(q,k,acts|None)->list[tuple[str,float]]
            store.py ChunkStore.save/load(path); get(ids)->list[LegalChunk] | router.py route(q)->set[str]
            rrf.py rrf(*ranked:list[str],k=60)->list[tuple[str,float]] | hybrid.py retrieve(q)->list[str] (top-20, 2 threads)
            reranker.py CrossEncoderLike(Protocol).score(q,list[str])->list[float]; CEReranker; FakeReranker(word overlap);
            rerank(q,chunks,top=5)->list[ScoredChunk]; is_confident(scored)->bool  (≥2 with score>THRESHOLD)
generation/ prompt.py build_prompt(q,chunks)->str (§7.1 verbatim + one fixed header-format line) | FALLBACK_MESSAGE
            llm.py LLMClient(Protocol).stream(prompt)->Iterator[str]; OllamaClient(httpx, temp 0.1); FakeLLM(scripted tokens); health()->bool
            parse.py split_sections(text)->ParsedResponse (case/ordering-tolerant; missing → "")
lang/       detect.py detect_lang(text)->"en"|"sw" | translator.py Translator(Protocol).translate(text)->str; MarianTranslator(direction); FakeTranslator(tag)
            glossary.py apply_glossary(sw_text)->str ("haki [right]") | pipeline.py to_english(q,lang)->str; to_user_lang(text,lang)->str
sessions.py SessionStore(ttl).create(SessionData)->str/get(id)->SessionData|None/update(...)  (dict + monotonic expiry)
letter.py   letter_text(parsed)->str; letter_docx(parsed)->bytes (python-docx)
main.py     create_app(deps: Deps)->FastAPI; Deps dataclass holds all interfaces (fakes injected in tests); routes:
            POST /api/query, GET /api/stream/{id} (SSE: token|done|error), GET /api/sources/{id}, GET /api/letter/{id}?fmt=txt|docx,
            GET /api/health, POST /api/feedback (→ data/feedback.jsonl)
## Pins (co-resolved in existing uv.lock → mutually compatible; py3.11, torch from CPU index)
fastapi==0.142.2 uvicorn[standard]==0.54.0 pydantic==2.13.5 pydantic-settings==2.15.0 httpx==0.28.1 sse-starlette==3.5.0
pdfplumber==0.11.10 sentence-transformers==6.1.0 faiss-cpu==1.15.1 whoosh==2.7.4 torch==2.14.1 transformers==5.18.0
sentencepiece==0.2.2 sacremoses (latest) langdetect==1.0.9 numpy==2.4.6 python-docx (latest, pin at M0) | dev: pytest==9.1.1 (no pytest-asyncio: 0.23 breaks on pytest 9; TestClient is sync)
## Ambiguities → defaults
- Constitution uses Chapters/Articles: parser treats CHAPTER as `part`, ActSpec.unit="Article" used in citations.
- Domain filter "narrows FAISS": IndexFlatL2 can't filter → faiss IDSelectorBatch over the routed Acts; same Act filter on BM25; if <5 hits, rerun unfiltered.
- "Translate back before streaming" vs token streaming: SW responses buffer the English stream, translate per section, emit as SSE chunks at end.
- Explicit language toggle (en/sw) overrides langdetect; "auto" uses langdetect (unreliable on short input).
- Prompt §7.1 lacks header instruction: append one fixed line naming the 3 headers; otherwise verbatim.
- Disclaimer added by API/frontend, never by the LLM. Fallback: QueryResponse.fallback=true, stream emits FALLBACK_MESSAGE, no LLM call.
- Feedback bar has no endpoint in §8 → add POST /api/feedback. Letter endpoint returns 409 until generation done.
- ">512 tokens" measured by MiniLM tokenizer in prod, word-count proxy in Fake. chunk_id = "{act_slug}:{num}" (+"-2" on duplicates). page = start page.
## Needed from you
1. Install Ollama and `ollama pull mistral:7b-instruct-q4_K_M` (not installed now). Needed only from M5 manual check / M7 health.
2. One-time internet for MiniLM, ms-marco cross-encoder, opus-mt-sw-en/en-sw (~1 GB) — tests never need them.
3. Act years + kenyalaw URLs (optional; PDFs already present so download step will just skip). I'll read years from the PDFs in M1 for you to confirm.
4. Confirm old frontend/ scaffold (Vite+TS) may be replaced in M8; confirm .docx/.pdf/legacy stay git-ignored.
