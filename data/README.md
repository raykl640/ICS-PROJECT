# data/

| Path | Contents | In git |
|---|---|---|
| `raw_pdfs/` | Source statute PDFs, one per Act listed in `backend/app/config.py` (`ACTS`). The corpus comes only from here. | No (not redistributed) |
| `processed/chunks.json` | Parsed `LegalChunk` records, written by `python -m backend.app.ingestion.build_index`. | No (generated) |
| `indexes/` | FAISS index + window map, Whoosh BM25 index. Rebuilt when any PDF's sha256 changes. | No (generated) |
| `feedback.jsonl` | Append-only thumbs up/down records (ids and ratings only, never question or answer text). | No |

If a PDF named in `ACTS` is missing, ingestion stops with an error rather than skipping the Act.
