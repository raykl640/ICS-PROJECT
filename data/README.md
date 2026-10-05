# data/

| Path | Contents | In git |
|---|---|---|
| `raw_pdfs/` | Source statute PDFs, one per Act listed in `data/sources.yaml` (loaded by `backend/app/config.py`). The corpus comes only from here. | No (not redistributed) |
| `processed/chunks.json` | Parsed `LegalChunk` records and `parse_report.md`, written by `python -m backend.app.ingestion.build_corpus`. | No (generated) |
| `indexes/` | FAISS index + window map, Whoosh BM25 index, written by `python -m backend.app.ingestion.build_index`. Each `meta.json` records the corpus hash; a stale index stops startup with the rebuild command. | No (generated) |
| `app.db` (+ `-wal`, `-shm`) | Local accounts (M13): usernames, display names, argon2id hashes, wrapped data keys, preferences; every content field (letter profile, and from M14 history) is AES-256-GCM ciphertext. Deleting the file deletes every account. | No (personal data) |
| `feedback.jsonl` | Append-only thumbs up/down records (ids and ratings only, never question or answer text). | No |

If a PDF named in `data/sources.yaml` is missing, ingestion stops with an error rather than skipping the Act.
