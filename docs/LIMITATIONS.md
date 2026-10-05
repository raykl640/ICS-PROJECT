# Known limitations

HakiAI gives **legal information, not legal advice**. This page lists what the system cannot do, or cannot do reliably,
so users, examiners and future maintainers can judge its answers. It follows ARCHITECTURE.md §7.4 (hallucination) and §8.2
(translation) and adds what was measured during the build.

## 1. Answers can still be wrong (hallucination)

- Retrieval-augmented generation reduces unsupported claims but does not remove them (ARCHITECTURE §7.4). Mistral 7B can
  combine two retrieved sections wrongly, attribute a rule to the wrong section, or draw a plausible conclusion that no
  section states.
- **Mitigations in place:**
  - The prompt tells the model to answer only from the five sections and to say when the answer is not there.
  - Temperature is 0.1.
  - Every cited Act and section is checked automatically against the five retrieved chunks. Unmatched citations trigger a
    warning banner.
  - The Sources panel shows the verbatim text so a reader can check each claim.
  - Every answer carries the disclaimer.
- **What the citation check cannot catch:** a correct citation attached to a wrong statement about that section;
  citations of Schedules (not extracted); claims made without any citation.
- **Truncation:** five long sections may not fit the 8192-token context. The lowest-ranked sections are shortened first, and
  the Sources panel flags them as truncated. The model may then miss a sentence that matters.
- **Null fallback:** the system refuses with a fixed message, and never calls the model, only when the question is
  out of scope by both checks: its MiniLM similarity to the in-scope examples (retrieval/scope.yaml) does not beat the
  out-of-scope ones by 0.06, and fewer than two chunks reach cross-encoder logit −2.0 (D21). On hand-written probe sets
  this answered 106 of 109 legal questions however worded (the 3 refused were Kiswahili/Sheng sent in EN mode, so not
  translated; in SW mode they are answered) and refused 60 of 63 unrelated ones. Remaining errors: foreign-law
  questions about covered topics ("eviction rules in New York") get an answer from Kenyan text, with Kenyan citations.
  Both values are provisional until tuned with human ground truth.

## 2. Kiswahili is best effort

- The MarianMT models were not trained on legal text (ARCHITECTURE §8.2). Swahili output is an aid, not an authoritative
  translation, and the UI says so on every Swahili answer.
- **Question translation:** the model named in the specification (opus-mt-sw-en) does not exist. Questions use
  opus-mt-swc-en (Congo Swahili), which renders some Kenyan legal words poorly: "kodi" (rent) became "tax" and "mwenye
  nyumba" (landlord) became "householder". Retrieval for Swahili questions is therefore weaker than for English ones.
- **Answer translation:**
  - Each sentence is translated separately, with citations, numbers, Act names and letter placeholders masked so they
    survive byte-identical.
  - A sentence whose placeholders the model destroys stays in English and is listed as untranslated.
  - Mixed English/Swahili answers are expected.
- **Unreviewed content:** the legal glossary (86 terms) and all Kiswahili UI strings were drafted without a legal translator
  and are marked `needs_human_review` ([HUMAN_TODO.md](HUMAN_TODO.md)).
- **Language detection:** detection on "auto" is unreliable for short or mixed text (Sheng is often detected as English). The
  user's explicit EN/SW choice always wins.

## 3. The corpus is small and frozen

- Only ten Acts are covered: the Constitution of Kenya 2010, the Employment Act, the Landlord and Tenant (Shops, Hotels and
  Catering Establishments) Act, the Rent Restriction Act, the Land Act, the Consumer Protection Act, the National Police
  Service Act, the Criminal Procedure Code, the Traffic Act and the Legal Aid Act. Subsidiary legislation, case law, county
  laws and practice directions are not included. A question outside these Acts gets the fallback, or a wrong-domain answer
  if the retrieved sections look similar.
- **Freshness:** the text is whatever revision of each PDF sits in `data/raw_pdfs/`. Amendments after that date are
  unknown to the system. Revision dates, from the FRBR expression date printed in each PDF (`data/sources.yaml`):

  | Act | Revision date |
  |---|---|
  | Constitution | 2010-09-03 |
  | Employment Act | 2024-04-26 |
  | Landlord and Tenant (Shops) Act | 2022-12-31 |
  | Rent Restriction Act | 2022-12-31 |
  | Land Act | 2025-11-04 |
  | Consumer Protection Act | 2022-12-31 |
  | National Police Service Act | 2023-09-15 |
  | Criminal Procedure Code | 2023-12-11 |
  | Traffic Act | 2024-04-26 |
  | Legal Aid Act | 2022-12-31 |
  - To update, replace the PDF, then run `python -m backend.app.ingestion.build_corpus` and
    `python -m backend.app.ingestion.build_index`. The startup check refuses stale indexes.
  - Repealed sections are detected only from their repeal note.
- **Parsing:** sections come from a regex parser over pdfplumber text. It was spot-checked by a human (M1 gate), but
  wrapped headings, tables (the CPC offence table) and Schedules can still be split or joined imperfectly. The Constitution
  preamble is not indexed.

## 4. Hardware and speed

- Built and measured on a laptop with a Ryzen 7 PRO 5850U (16 threads), 15 GiB RAM and no GPU.
  - Retrieval + reranking: p50 855 ms.
  - A cold first answer: 78–219 s to the first token and 151–304 s in total over two measured runs (M7 and M10). Ollama
    loads the 4.1 GB model and evaluates a ~2,300-token prompt on the CPU; the run-to-run variance was not investigated.
  - Warm answers are faster but still take tens of seconds. The specification's "first token in 2–3 s" goal is not met
    on CPU-only hardware.
- **Minimum:** 8 GB RAM is the floor for Mistral 7B Q4 plus the four local models (≈ 4.1 GB for the LLM, about 1 GB for the
  others). With 8 GB, close other applications. Slower CPUs scale the times above roughly linearly.
- **Concurrency:** only one answer is generated at a time. Others wait in a queue of at most 8, then get "busy". The system
  is meant for one person or a small office on one machine, not as a public web service.
- **Platform:** Linux is tested. Windows support (`scripts/run.ps1`, the non-POSIX feedback lock) is written but untested.
  The Docker files are validated with `docker compose config` but were not built on the development machine.

## 5. Evaluation is incomplete

The evaluation harness is built and tested, but the results that answer research question 5 need human input that does not
exist yet:
- the 15-question retrieval ground truth;
- three raters' grounding and accuracy scores;
- the usability survey;
- the functional and latency runs on the laptop with Ollama.

Until then there are no retrieval-precision, accuracy or SUS numbers to report. See [HUMAN_TODO.md](HUMAN_TODO.md).

## 6. Other boundaries

- **Sessions and rate limits:** both are held in memory, so a restart forgets them. Running several server processes would
  give each its own sessions.
- **No accounts and no history:** the system keeps no record of users or past answers. The only persisted user data is the
  optional thumbs-up/down feedback (ids, rating, an optional comment).
- **Referral contacts:** the "where to get help" block stays hidden until a human adds verified agencies
  (`config/referral_resources.json`).
