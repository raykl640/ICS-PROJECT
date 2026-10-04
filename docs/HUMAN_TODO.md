# Needed from a human
Items Claude must not invent (statute text, ground truth, agency contacts, verified Swahili legal terms). One line each: what, why, where it is used.

- M1 review gate: run `python scripts/inspect_chunks.py --per-act 20`, compare with the PDFs, read data/processed/parse_report.md, then `mkdir -p .gates && touch .gates/M1-reviewed.ok`. Used by: M2 start.
- Optional: verified direct kenyalaw.org PDF links for data/sources.yaml (all `url: null`; I was not certain of the exact download paths). Used by: ingestion/download.py when a PDF is missing.
- Optional: a Kiswahili speaker to check the routing hints in backend/app/retrieval/domains.yaml (mwajiri, mshahara, mpangaji, mwenye nyumba, dhamana, ...). They are everyday words used only to pick Acts, never shown to users as legal terms. Used by: router (Swahili questions are translated first, so impact is small).
