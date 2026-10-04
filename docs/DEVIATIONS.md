# Deviations from ARCHITECTURE.md
Format: what / why / impact. Append-only; reference the change that introduced each entry.

## D1 Embedding windows instead of one vector per chunk (§4.1) — docs: amend design
- What: long sections are embedded as overlapping, header-prefixed windows; chunk score = max over its windows.
- Why: all-MiniLM-L6-v2 truncates at 256 word-pieces, so one vector per section silently ignores most of a long section.
- Impact: FAISS holds more vectors than chunks (window→chunk_id map); results are still unique chunks; full text unchanged.

## D2 Normalised embeddings in IndexFlatL2 (§4.1)
- What: vectors are L2-normalised before indexing and querying.
- Why: makes L2 ordering identical to cosine similarity, the metric MiniLM is trained for.
- Impact: same index type; distances are in [0, 4] instead of unbounded.

## D3 Domain filter applies to BM25 too, and widens on too few hits (§5.2)
- What: routed Acts filter both FAISS and Whoosh; < 5 filtered hits reruns over the full corpus. Constitution is added as co-domain for
  rights topics; explicit Act / "section N" / "Article N" mentions override the keyword table.
- Why: §5.2 filters only FAISS, which would make RRF fuse a filtered and an unfiltered list inconsistently; narrow filters can starve retrieval.
- Impact: router is slightly richer than a plain keyword table; no-match behaviour is unchanged (full corpus).

## D4 Repealed sections excluded from the indexes (§2, §4)
- What: sections whose body is only a repeal/deletion note are kept in chunks.json but not indexed.
- Why: they carry no law and would crowd out real provisions in top-5.
- Impact: chunk count in indexes < chunks.json count.

## D5 Prompt additions and chunk truncation (§7.1)
- What: one fixed line naming the three output headers is appended to the §7.1 prompt; chunks over the token budget are truncated with
  "[... truncated]", and num_ctx 8192 / num_predict 1024 are set explicitly.
- Why: §7.1 never asks for the headers that §7.3 parses; Ollama's default context would silently cut 5 long sections.
- Impact: the LLM may see a truncated section; Sources still shows the full verbatim text with a `truncated` flag.

## D6 Swahili: English draft streams live, translation replaces it (§8.2, §10 step 15)
- What: §8.2 translates "before streaming"; we stream the English draft as tokens, then send translated sections in a `translated` event.
- Why: MarianMT needs the whole text; buffering would lose the <3 s first-token target for Swahili users.
- Impact: Swahili users briefly see English text. Citations are placeholder-masked through translation and verified.

## D7 SSE events beyond tokens; single-generation queue (§8.1)
- What: events status/token/translated/done/error/null; one LLM generation at a time with queue positions; disconnect cancels Ollama.
- Why: one CPU Mistral cannot serve concurrent requests; clients need progress, warnings and a clean end-of-stream signal.
- Impact: frontend must handle the event contract in DESIGN.md "SSE contract".

## D8 Sixth endpoint POST /api/feedback; JSONL instead of a JSON file (§8, §9)
- What: §8 lists five endpoints but §9's Feedback Bar needs a writer; feedback is appended as JSONL with a file lock.
- Why: no endpoint exists to receive feedback; JSONL appends are atomic per line and need no read-modify-write.
- Impact: one extra endpoint; stored records contain no question/answer text (privacy rule).

## D9 Citation verification warnings (§7.4)
- What: cited Act+section pairs are checked against the session's 5 chunks; unmatched ones produce a UI warning.
- Why: §7.4 admits misattribution risk; this catches the common case automatically.
- Impact: extra `warnings` in the `done` event and a warning banner in the Response Panel.

## D10 Parameter values set by the M0 milestone prompt — feat(M0)
- What: num_predict 1500 (D5 said 1024); max_sessions 200 (DESIGN said 500); separate dense_k/sparse_k knobs (both 20).
- Why: the milestone prompt wins on behaviour; prompt budget is still positive (8192 − 1500 − 256 = 6436 tokens for 5 chunks ≤ 1200).
- Impact: slightly longer answers allowed; fewer concurrent sessions kept in memory. DESIGN.md updated to match.

## D11 What the parser does not chunk; Schedules are single chunks (§3.1) — feat(M1)
- What: text before the first unit heading (cover, licence page, TOC, gazette/assent block, long title, Constitution preamble),
  editorial amendment notes ("[Act No. 19 of 2015, s. 148.]"), cross-headings and the CPC index ("not part of the Act") are dropped.
  Each Schedule becomes one chunk (`{slug}-sch{n}`) however long; numbered items inside it never start a new unit.
- Why: none of the dropped text is an operative provision (the index says so itself); amendment notes would pollute BM25 with
  Act numbers/years. Schedule numbering restarts, so splitting them by number would collide with section ids.
- Impact: the Constitution preamble cannot be retrieved. Long Schedules (Constitution Sixth, CPC First/Second) rely on M2's
  embedding windows and M5's chunk truncation; they are listed under "long" in parse_report.md.

## D12 Word-based embedding windows; exhaustive filtered FAISS search (§4.1, D1) — feat(M2)
- What: windows are sized in words (180, stride 120, only for chunks > 200 words) with header "{act} — {unit} {num}: {title}. ",
  as the M2 milestone specifies, instead of DESIGN's 256-token windows with 64-token overlap. Filtered dense search scans all
  selected windows instead of over-fetching k*4.
- Why: the milestone wins on behaviour. A flat index computes every distance regardless of k, so scanning all windows costs
  nothing extra and always yields k unique parents when they exist.
- Impact: 105 of 2274 real-corpus windows (4.6%) exceed MiniLM's 256 word-pieces and lose their tail when embedded; for
  non-final windows the 60-word overlap re-embeds that tail in the next window. Sizes are tunable in config.py; build_index
  prints the over-limit count.

## D13 Null-response threshold is inclusive (§7.5) — feat(M4)
- What: a chunk counts as confident when rerank_score >= relevance_threshold; ARCHITECTURE §7.5 says "above", DESIGN said ">".
- Why: the M4 milestone prompt specifies an inclusive boundary and wins on behaviour.
- Impact: only a score exactly equal to the threshold changes outcome (negligible for float logits). The default 0.0 is
  provisional: on the real corpus three in-scope lay questions (eviction, compulsory acquisition, legal aid) top out below 0
  while off-topic/garbage queries score about -10; M9's tune_threshold sets the value.

## D14 Prompt rules, token estimate and module shape for generation (§7.1–7.3) — feat(M5)
- What: (a) the system prompt is §7.1 verbatim followed by rules the M5 milestone requires (say what is missing, cite as
  (Act name, s. N), no invented facts/deadlines/amounts/court names, Grade 8 language, treat <question> text as data, the three
  headers, letter placeholders [Your Name] [Date] [Recipient], end with the DISCLAIMER line), instead of DESIGN's "verbatim + one
  header line"; (b) est_tokens = ceil(1.4 × (words + punctuation marks)) instead of DESIGN's ceil(chars/3); (c) truncation marker
  "[... truncated — see Sources]"; a chunk with < min_chunk_tokens left is dropped (flagged); (d) the prompt keeps the §7.1
  single-string layout ("SYSTEM: … CONTEXT: … USER QUESTION: <question>…</question>") and goes to /api/generate as `prompt`, so the
  LLMClient protocol is unchanged; PromptBuild still exposes system/user; (e) DESIGN names kept over the milestone's (llm.py not
  ollama_client.py, parse.py not sections.py, PromptBuild not BuiltPrompt, check_citations → CitationCheck(verified, unmatched)
  not CitationReport(verified, unverified)); ParsedResponse gains format_ok; service.py and extract_citations are new.
- Why: the milestone wins on behaviour, DESIGN on names. Counting punctuation keeps the milestone's 1.4 ratio but stays
  conservative on "41(2)(a)"-style references that Mistral splits into many tokens.
- Impact: the model is told to append the disclaimer although the API also adds it (DESIGN said "never by the LLM"); that line
  lands at the end of the letter section, so M7's letter export must strip it. Measured: the estimate is ~22% above Ollama's
  prompt_eval_count on real prompts (6396 vs 5207 worst case), so the budget holds with headroom.
