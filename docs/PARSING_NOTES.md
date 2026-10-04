# Parsing notes (M1 inspection of data/raw_pdfs, 2026-10-04)
Written before the parser, from pdfplumber text of every page of all 10 PDFs. Re-check this file if a PDF is replaced.

## Source format
All 10 PDFs are the current Kenya Law / Laws.Africa consolidated layout ("Legislation as at <date>", FRBR URI on page 2).
All are text-searchable: no page has < 50 extracted characters, so no OCR is needed for the current corpus.

| Act | pages | FRBR URI (year = Act year) | Cap | as at |
|---|---|---|---|---|
| Constitution of Kenya | 143 | /akn/ke/act/2010/constitution | — | 2010-09-03 |
| Employment Act | 45 | /akn/ke/act/2007/11 | 226 | 2024-04-26 |
| Landlord and Tenant (Shops, Hotels and Catering Establishments) Act | 13 | /akn/ke/act/1965/13 | 301 | 2022-12-31 |
| Rent Restriction Act | 22 | /akn/ke/act/1959/35 | 296 | 2022-12-31 |
| Land Act | 90 | /akn/ke/act/2012/6 | 280 | 2025-11-04 |
| Consumer Protection Act | 37 | /akn/ke/act/2012/46 | 501 | 2022-12-31 |
| National Police Service Act | 61 | /akn/ke/act/2011/11a | 84 | 2023-09-15 |
| Criminal Procedure Code | 223 | /akn/ke/act/1930/11 | 75 | 2023-12-11 |
| Traffic Act | 69 | /akn/ke/act/1953/39 | 403 | 2024-04-26 |
| Legal Aid Act | 33 | /akn/ke/act/2016/6 | 16A | 2022-12-31 |

The Act years in config match the FRBR URIs (resolves the M0 open issue).

## Page layout
- Page 1 cover ("LAWS OF KENYA ... CAP. 226"), page 2 licence/FRBR page, then a "Contents" TOC (2–12 pages) whose entries end in
  dot leaders and a page number (`41. Notification and hearing ... 23`). Long TOC entries wrap and the leader moves to the next line.
- Body pages: first line is a running header `<Act title> (Cap. N) Kenya` (Constitution: `Constitution of Kenya Kenya`;
  TOC pages: `<Act title> (Cap. N)`), last line is the bare page number. No "[Rev. ...]" lines in this format (kept as a
  noise pattern for older kenyalaw PDFs).
- Body opens with the gazette/assent block and `[Amended by ...]` history, then the long title ("An Act of Parliament to ..."),
  then the first Part/Chapter. All of this precedes the first unit heading and is not chunked (Constitution preamble likewise).

## Units and headings
- Section/Article heading = its own line `N. Title` / `41A. Title` (title on the same line). Subsections follow as `(1)`, `(a)`, `(i)`
  at line start. Titles ≥ ~60 chars wrap; the continuation line starts lowercase (Land s.33, Traffic s.48, a few in CPC and NPS).
- Repealed/spent units: `8. [Repealed by Act No. 2 of 1970, s. 9.]`, `31A. [Deleted by Act No. 20 of 2020 Sch.]`, `91. [Spent]`
  (title is the note, no body).
- Editorial amendment notes end many sections: `[Act No. 19 of 2015, s. 148.]`, `[L.N. ...]`, sometimes wrapping over 2–5 lines.
  They are not statute text → stripped (multi-line until the closing `]`).
- Parts: `Part I – PRELIMINARY`, `Part 1 – PRELIMINARY`, `Part IXA – ...`, `Part VII – Repealed`. Long Part titles wrap onto an
  uppercase line (`Part V – MODE OF TAKING AND` / `RECORDING EVIDENCE ...`). Body false positives exist (`Part but in other respects`,
  `Part.`) → Part regex requires `Part <roman|digit> – <title>`.
- Cross-headings between sections (CPC `Arrest Generally`, `SENTENCE OF DEATH`; Land `Transfers`; Constitution Part-title wraps)
  sit on their own line before a heading; they are not part of the previous section's text.
- Constitution: `Chapter Four` alone on a line, title on the next line (`THE BILL OF RIGHTS`), then `Part 1 – ...` inside Chapters.
  264 Articles. `Chapter Fifteen applies;` is a body false positive (wrapped text) → chapter regex requires the whole line.
- No sub-Parts/Divisions; no footnotes in this layout. Numbered heading candidates are monotonic in every Act body except inside
  Schedules (where numbering restarts) — verified by script: 0 out-of-order outside Schedules and TOCs.

## Schedules
- `FIRST SCHEDULE`, `SECOND SCHEDULE [s. 25]`, `SCHEDULE [s. 3]`; next line is the title (`COUNTIES`, `REPEALED`, `SPENT`, `DELETED`).
  Constitution has six (I–VI); NPS eight (Second/Third repealed); CPC four (Third spent, Fourth repealed); others one.
- Inside Schedules numbering restarts (`1. Mombasa`, `2. – ACCESSORY AFTER THE FACT TO MURDER`, NPS rules `1. ...`) → numbered lines
  inside a Schedule never start a new unit. Each Schedule becomes one chunk (`unit_type="schedule"`).
- CPC First Schedule is an offences table (column text is interleaved by pdfplumber) and the Second Schedule holds charge forms
  with dot-leader blanks (`on the ........ day of`). Both are long; flagged in parse_report.md for human review.
- CPC pages ~134–222: `INDEX TO THE CRIMINAL PROCEDURE CODE` ("not part of the Act") → skipped until the next Schedule heading.

## Text hygiene decisions
- Quotes: “ ” → `"`, ‘ ’ → `'`. Dashes: – ‒ ― − ‐ ‑ → `-`; em dash `—` kept (used as "the right—"). NFKC + non-breaking spaces.
- Line ends with a hyphen (40 cases) are real compounds (`co-ordination`, `non-discrimination`, `twenty-four`, `vice-chairperson`):
  joined without a space and the hyphen is kept. No soft (typesetter) hyphenation found.
- Wrapped lines are joined with a space; a new line is kept before subsection markers `(1) (1A) (a) (aa) (iv)`, quoted definitions,
  numbered paragraphs and uppercase sub-headings (Schedules).

## Profiles
- default: unit "section", Part tracking, no Chapters, header `... (Cap. N) Kenya`.
- constitution-of-kenya: unit "article", Chapter tracking (Part resets at each Chapter), header `Constitution of Kenya Kenya`.
- Skip-block `INDEX TO THE ...` and editorial-note stripping are in the default profile (only CPC has an index today).
