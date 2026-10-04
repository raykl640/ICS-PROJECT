# Extra instructions to append to the template for specific milestones

M1 Ingestion: Statute PDFs are in data/raw_pdfs/ (I supply them). Parser must drop table-of-contents entries, running headers/footers and
  footnotes; capture Part headings; keep subsections inside their parent section. Write tests on tiny synthetic PDFs (generate with reportlab).
  Also write scripts/inspect_chunks.py that prints N random chunks per Act with page numbers so I can review them. Then STOP for my review.
M3 Retrieval: RRF test must use hand-computed scores for at least two lists with overlap. Router keyword table lives in config and covers all 9 Acts.
M5 Generation: parser must survive missing/duplicate/reordered headers and extra whitespace; add 8+ malformed-output test cases.
M6 Language: glossary of 60+ legal terms EN->SW in a JSON file; translators only load models lazily on first Swahili query.
M7 API: SSE must stream with FakeLLM in tests; test session expiry, unknown session_id (404), null fallback path, and Swahili round trip with fakes.
M8 Frontend: use the frontend-design skill; mobile-first, calm, high-contrast; disclaimer always visible; accessibility (labels, focus, aria-live for streamed text).
   Add vitest tests for the SSE hook and tab splitting. Build output served by FastAPI at /.
M9 Evaluation: I will give you eval/ground_truth.json. You write the harness: P@5 for FAISS-only, BM25-only, hybrid; a grounding checker that verifies every
   "Act, Section N" citation in a response exists in that session's 5 chunks; output eval/report.md with tables.
