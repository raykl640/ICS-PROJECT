# Build plan — one milestone per session (/clear between them)

## Decisions (resolve spec inconsistencies; change here if you disagree)
- Response time target: first token <3 s, full response 40–120 s on CPU (docs disagree; don't test on it).
- Relevance threshold for null fallback: cross-encoder score > 0 (tunable in config.py, tuned in M9).
- Sessions: in-memory dict with 1-hour expiry. Feedback: append-only JSONL at data/feedback.jsonl.
- Letter export: plain text + DOCX via python-docx.
- Section-aware chunking: sections are stored whole; long ones are embedded as overlapping header-prefixed windows (see DESIGN.md "Retrieval").
- Layout: fresh build in backend/app/ per CLAUDE.md; the earlier untracked app/, scripts/, tests/ etc. move to legacy/ (git-ignored, reference only) at the start of M0.
- Corpus = 10 Acts: the 9 in ARCHITECTURE.md §2 + Legal Aid Act (the proposal's scope names only 2; the architecture is newer). PDFs live in data/raw_pdfs/ (rename from data/raw/ in M0).
  Expanded to 25 Acts after M15 at the owner's request (DEVIATIONS D32).
- Full M0–M7 signatures and further ambiguity defaults: see docs/DESIGN.md.

## Milestones (each ends: tests green, commit, PROGRESS.md updated)
M0 Scaffold: repo layout, config.py, models.py (LegalChunk dataclass/pydantic), requirements, pytest + CI script, Fake interfaces.
M1 Ingestion: download script (URL list in config; skips if file exists), pdfplumber text extraction, Part/section regex parser,
   noise filters (TOC, footers). Output data/processed/chunks.json. Test on small fixture PDFs in tests/fixtures.
   >> HUMAN REVIEW GATE: spot-check 20 chunks per Act against the PDF.
M2 Indexes: embed + FAISS persist/load; Whoosh BM25 build/search; chunk store keyed by chunk_id. Tests with fake embedder.
M3 Retrieval: keyword domain router, dense+sparse parallel search, RRF (k=60) with unit tests on hand-computed scores.
M4 Rerank: cross-encoder wrapper (+fake), top-20→top-5, threshold + null fallback logic.
M5 Generation: prompt builder, Ollama streaming client (+fake), section-header parser (handles missing/misordered headers).
M6 Language: langdetect, MarianMT wrappers, glossary with bracketed English; sw→en before retrieval, en→sw after generation.
M7 API: 5 endpoints, SSE, sessions, letter text/DOCX, health. Integration tests via FastAPI TestClient with fakes.
M8 Frontend: Query, Response (3 tabs, streaming), Sources panel, Feedback bar, disclaimer, null-response screen. Served as static build by FastAPI.
M9 Evaluation: eval/ with 15 retrieval queries (FAISS vs BM25 vs hybrid, P@5), 20 functional queries (5 Swahili), grounding checker script.
   >> HUMAN GATE: you write the ground-truth sections for the 15 retrieval queries.
M10 Docs & hardening: README, setup script, error handling, final full test run.

## v2 — product rework (M11–M18; spec: docs/DESIGN_V2.md, prompts: prompts/milestones/M11–M18.md)
Owner decisions (2026-10-05): pywebview + PyInstaller desktop app (Windows .exe via Inno Setup, Linux AppImage + .deb);
small installer + first-run setup wizard + USB offline bundle; local accounts with per-account encrypted history (recovery
code); daily highlights = curated corpus sections + local-LLM blurbs, flagged until a human approves them.
M11 Design language: 3 directions, tokens, Radix primitives, style guide, screenshots.  >> HUMAN GATE: pick a direction (.gates/M11-design.ok)
M12 App shell + routing + Ask v2 on the chosen design (guest mode), settings, "How it works".
M13 Local accounts: SQLite, argon2id, AES-GCM per-user keys, recovery code, auto-lock, guest/private modes, export/delete.
M14 Conversations with follow-ups, background answers + notifications, library, letter workspace, matters, bookmarks, notes.
M15 Laws browser/reader with cross-references, full-text search, command palette.
M16 Knowledge of the day, life-situation guides, glossary browser.  >> HUMAN GATE: review highlights/topics (.gates/M16-content-reviewed.ok, before M18)
M17 Desktop app: launcher, setup wizard, managed Ollama, offline bundle, PyInstaller, Inno Setup, AppImage/.deb, CI matrix.
M18 Polish, onboarding, accessibility audit, docs, v2.0.0.
