# HakiAI (KenyaLegalAid) — project memory

Offline RAG legal-information assistant for Kenyan citizens (EN + Kiswahili).
Full spec: @docs/ARCHITECTURE.md  |  Milestones: @docs/BUILD_PLAN.md  |  Status: @docs/PROGRESS.md
Do NOT read the original proposal .docx or the statute PDFs unless a task says so. Everything needed is in docs/.

## Stack (fixed — do not substitute)
Python 3.11, pdfplumber, sentence-transformers (all-MiniLM-L6-v2), FAISS IndexFlatL2, Whoosh BM25,
cross-encoder/ms-marco-MiniLM-L-6-v2, Ollama (mistral:7b-instruct Q4_K_M), FastAPI + SSE,
MarianMT (opus-mt-sw-en / en-sw), langdetect, React + Vite + Tailwind. Tests: pytest, vitest.

## Layout
backend/app/{main,config,models,sessions,letter}.py
backend/app/{ingestion,retrieval,generation,lang}/   (one module per pipeline stage)
backend/tests/   frontend/   data/{raw_pdfs,processed,indexes}/   eval/   docs/

## Commands
- Install: `pip install -r backend/requirements.txt`; `cd frontend && npm i`
- Test backend: `pytest backend/tests -q -x`   (must pass before every commit)
- Run API: `uvicorn backend.app.main:app --reload`
- Build index: `python -m backend.app.ingestion.build_index`
- Eval: `python eval/run_eval.py`

## Hard rules
1. Every external heavy dependency (Ollama, embedding model, cross-encoder, MarianMT) sits behind a small
   interface in its module with a Fake implementation for tests. Tests must run with NO model downloads and NO Ollama.
2. Prompt is exactly as in ARCHITECTURE.md §7.1; temperature 0.1; output headers `## RIGHTS EXPLANATION`,
   `## RECOMMENDED STEPS`, `## FORMAL LETTER`. If <2 chunks above threshold → fixed fallback message, never call the LLM.
3. Never invent statute text. Corpus comes only from files in data/raw_pdfs/. If a PDF is missing, stop and say so.
4. Config (paths, k=60, top-20/top-5, threshold, model names, ports) lives only in config.py.
5. Type hints everywhere, small functions, no dead code, no TODO left without an entry in PROGRESS.md.

## Workflow rules (token efficiency)
- Work on ONE milestone at a time from BUILD_PLAN.md. Read only the files that milestone touches.
- Write the test first, then the code; run only the relevant test file while iterating, full suite at the end.
- Don't re-read files you just wrote. Don't print large outputs: use `| tail -n 30`, `-q`, `--maxfail=1`.
- Use Grep/Glob, not full-repo reads. Delegate wide searches to a subagent.
- At milestone end: run full tests, commit (`feat(Mx): ...`), update docs/PROGRESS.md (done / decisions / next), then stop.
- Commits are authored solely by the repo owner (git config user). No `Co-Authored-By` or other AI/Copilot/Claude attribution trailers in commits or PRs.
- If a spec ambiguity blocks you, pick the default in BUILD_PLAN.md "Decisions", record it in PROGRESS.md, continue.
