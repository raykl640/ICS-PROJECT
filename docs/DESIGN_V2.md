# HakiAI v2 design (M11–M18): accounts, library, laws browser, daily highlights, desktop app
Read with docs/DESIGN.md (v1, still authoritative for the RAG pipeline, SSE contract and privacy rules). This file wins on
v2 names/signatures. Owner decisions (2026-10-05): pywebview + PyInstaller desktop shell; small installer + first-run setup
wizard (with USB offline-bundle import/export); per-account encrypted history; daily highlights = curated corpus sections +
local-LLM blurbs flagged until a human approves them.

## Users and constraints that drive every choice
- Kenyan citizens with no legal training; mixed literacy; EN and Kiswahili; often shared or cyber-café computers; low-end
  laptops (4–8 GB RAM, no GPU); intermittent or no internet after setup.
- Answers take 1–4 minutes on CPU (PROGRESS M7/M10). The UX must treat generation as a background job, not a spinner.
- Rules carried over unchanged: offline at runtime, no fabricated legal content, verbatim sources next to every answer,
  disclaimer on every answer, no content in logs, prompt §7.1, null fallback never calls the LLM.

## Information architecture (routes; react-router)
| Route | Screen | Notes |
|---|---|---|
| `/setup` | First-run wizard (desktop only) | Ollama + models check/download/import; shown until preflight is green |
| `/welcome`, `/signin`, `/signup`, `/recover` | Auth | Account tiles optional; "Continue as guest" always visible |
| `/` | Home | Composer, Knowledge of the day, Continue (recent chats/letters), topic tiles, bookmarks |
| `/ask`, `/ask/:conversationId` | Conversation | Threaded turns; answer card (Rights / Steps / Letter tabs), Sources drawer, follow-up composer |
| `/library` (`?tab=chats|letters|saved|notes`) | Library | Search, filter (Act, matter, date, language), sort, pin, rename, delete, export |
| `/matters/:id` | Matter (case folder) | Chats, letters, notes, bookmarks for one dispute; status (open/closed) |
| `/letters/:id` | Letter workspace | Editable text, placeholder fill from profile, versions, DOCX/TXT/print |
| `/laws`, `/laws/:act`, `/laws/:act/:chunkId` | Laws browser + reader | TOC by Part/Chapter, verbatim text, cross-refs, "Ask about this", bookmark, note |
| `/search?q=` | Full-text search | BM25 hits with highlighted snippets, Act filter; also reachable from Ctrl+K |
| `/today`, `/today/archive` | Knowledge of the day | Today's highlight + past ones |
| `/topics`, `/topics/:slug` | Life-situation guides | Curated section lists ("Fired or mistreated at work", "Renting a home", ...) |
| `/glossary` | EN↔SW legal glossary | Shows review status of each term |
| `/settings` (`?tab=profile|appearance|language|privacy|system|about`) | Settings | Account, letter profile, theme, text size, auto-lock, data export/delete, model status |
Layout: left sidebar (collapsible to icons; bottom sheet nav < 768 px), top bar with global search (Ctrl/Cmd+K command palette),
account menu with Lock / Sign out. Desktop-first, responsive to 360 px (Docker/web still supported).

## Design language (M11 picks one of three directions; human gate)
- Tokens only (CSS variables on :root, `[data-theme=dark|light]`, `[data-contrast=more]`, `[data-text=sm|md|lg|xl]`), mapped
  into Tailwind 4 `@theme`. No raw hex in components (lint rule / test greps components for `#[0-9a-f]{3,6}`).
- Fonts bundled offline with @fontsource packages (OFL): one UI sans, one reading serif for statute text; system fallbacks.
- Contrast: a vitest computes WCAG ratios for every declared fg/bg token pair in all themes; body text ≥ 7:1 (AAA) in the
  reading view, everything else ≥ 4.5:1, UI borders/focus ≥ 3:1.
- Performance on WebKitGTK/WebView2 and low-end CPUs: no backdrop blur, no large shadows on scrolling content, animations
  ≤ 200 ms and disabled under prefers-reduced-motion or the in-app "Reduce motion" setting.
- Copy: sentence case, plain words ("What the law says", "What you can do", "Draft letter"), every string in
  backend/app/lang/ui_strings.json (EN + SW, SW flagged for review).
- Primitives: Radix UI (dialog, dropdown-menu, tabs, tooltip, popover, toast, toggle-group, scroll-area) for focus/keyboard/ARIA;
  icons lucide-react. Own components: Button, IconButton, Field, TextArea, Select, Card, Badge, Kbd, Skeleton, EmptyState,
  ProgressSteps, AnswerCard, SourceCard, LawText, CommandPalette, Sidebar, TopBar, SplitView.
- Bundle budget: initial route ≤ 200 KB gzipped JS; every other route lazy-loaded; report sizes in PROGRESS.

## Accounts and encrypted store (backend/app/accounts/)
- `db.py`: SQLite (stdlib sqlite3, WAL, foreign keys on) at `settings.app_db_path`; numbered migrations in `migrations/NNN_*.sql`,
  applied on startup, version in `PRAGMA user_version`. One connection per request via a dependency; writes serialized.
- `crypto.py`: password hash = argon2id (argon2-cffi PasswordHasher, params in config). Per-user random 256-bit DEK.
  KEK_pw = argon2id raw(password, kek_salt); KEK_rc = argon2id raw(recovery_code, rc_salt). DEK stored twice, wrapped with
  AES-256-GCM (cryptography) under each KEK. Every content field = AES-GCM(DEK, nonce‖ciphertext, AAD = table:column:row_id).
- Recovery code: 20 random base32 chars shown once in groups of 4 (copy / print / save .txt); used to reset the password, then
  a new code is issued. Lost password + lost code = history unrecoverable (said plainly at signup).
- Unlocked DEKs live only in server memory, in `AuthSessions` keyed by a 256-bit token (cookie `haki_auth`, HttpOnly,
  SameSite=Strict, Path=/api; Secure when served over https). Server restart, sign-out, lock or `auto_lock_s` idle (default
  900) drops the DEK; the UI shows a lock screen asking only for the password.
- Login throttling: `login_max_attempts` (5) per username then exponential lockout from `login_lockout_s` (30); generic error text.
- Guest mode: no account, nothing persisted (exactly v1 behaviour). Signed-in users can turn "Save history" off (private mode).
- Localhost hardening (desktop serves on 127.0.0.1): Host header must be an allowed host:port (DNS rebinding); every mutating
  /api request needs header `X-Haki: 1` (forces CORS preflight, which is refused); no CORS in prod.
- Privacy rule extension: content is persisted only encrypted, only for signed-in users with history on (D22). Logs unchanged.
- Tables (all `*_ct` are ciphertext BLOBs; ids are UUID4 text; times are UTC ISO strings set by the injected clock):
  users(id, username UNIQUE (casefolded), display_name, pw_hash, kek_salt, dek_pw, rc_salt, dek_rc, prefs_json, created_at,
  failed_logins, locked_until) · profiles(user_id, data_ct)  [name, address, phone, email, id no. for letters] ·
  matters(id, user_id, name_ct, status, created_at, updated_at) · conversations(id, user_id, matter_id?, title_ct, pinned,
  lang, created_at, updated_at) · turns(id, conversation_id, idx, question_ct, answer_ct, sources_ct, meta_ct, null_response,
  created_at) · letters(id, user_id, matter_id?, conversation_id?, title_ct, created_at, updated_at) · letter_versions(id,
  letter_id, n, body_ct, created_at) (keep `letter_versions_max` 20) · bookmarks(id, user_id, chunk_id_ct, matter_id?,
  created_at) · notes(id, user_id, target_kind, target_ct, body_ct, matter_id?, updated_at) · reads(user_id, chunk_id_ct, at)
  (last 50, for "Continue reading").
- Library search: decrypt the user's rows in memory after unlock and filter there (expected size: hundreds of rows).

## API v2 (all JSON; errors {"error":{code,message}}; existing v1 endpoints unchanged unless noted)
- Auth: POST /api/auth/register {username, password, display_name} → {user, recovery_code} · POST /api/auth/login ·
  POST /api/auth/logout · POST /api/auth/lock · POST /api/auth/unlock {password} · GET /api/auth/me (404-free: {user|null,
  locked}) · POST /api/auth/recover {username, recovery_code, new_password} → {recovery_code} · POST /api/auth/password.
- Account: GET/PUT /api/account/profile · GET/PUT /api/account/prefs · GET /api/account/export (decrypted JSON download) ·
  DELETE /api/account {password} (rows deleted, VACUUM).
- Conversations: GET /api/conversations?q=&matter=&cursor= · GET/PATCH/DELETE /api/conversations/{id}.
  POST /api/query gains `conversation_id?` and `background` (default true when signed in). A done turn is saved by the server.
- Background runs (D24): signed-in runs continue when the client disconnects and are saved on completion; DELETE
  /api/sessions/{id} stops a run (closes the Ollama stream). GET /api/events (SSE, per auth session): `turn_done`,
  `turn_failed` {conversation_id, turn_id} → in-app toast + OS notification (Notification API; desktop shell bridges it).
  Guests keep v1 semantics (disconnect = abort).
- Follow-ups (D23): retrieval query = previous question + current question (retrieval only, last `followup_context_turns`=1);
  the §7.1 prompt is unchanged except USER QUESTION is "Earlier question: …\nQuestion: …". Null fallback rule unchanged.
- Letters: GET/POST /api/letters · GET/PUT/DELETE /api/letters/{id} (PUT adds a version) · GET /api/letters/{id}/versions ·
  GET /api/letters/{id}/export?format=docx|txt. Placeholders "[Your name]" etc. map to profile fields (client-side fill,
  preview before applying). Print uses a print stylesheet.
- Saved items: GET/POST/DELETE /api/bookmarks · GET/PUT/DELETE /api/notes · GET/POST/PATCH/DELETE /api/matters.
- Laws (public, no auth): GET /api/laws → [{slug, name, year, unit, sections, repealed}] · GET /api/laws/{slug} → TOC
  [{part, items:[{chunk_id, num, title, repealed}]}] · GET /api/laws/sections/{chunk_id} → {chunk, prev, next,
  refs_out:[{label, chunk_id?}], refs_in:[chunk_id]} (refs via RefExtractor; computed at index build into
  data/indexes/refs.json) · GET /api/search?q=&acts=&limit= → {hits:[{chunk_id, act, num, title, snippet, marks:[[s,e]]}]}
  (Whoosh BM25 on the sparse index; marks are offsets, never HTML).
- Highlights/topics/glossary (public): GET /api/highlights/today?date=YYYY-MM-DD (client local date, validated) ·
  GET /api/highlights?until=YYYY-MM-DD · GET /api/topics · GET /api/topics/{slug} · GET /api/glossary?q=.
- Setup (desktop_mode only, localhost only): GET /api/setup/status · POST /api/setup/ollama {action: use_system|install} ·
  POST /api/setup/models · GET /api/setup/progress (SSE: step, bytes, total, eta, error) · POST /api/setup/bundle/import
  {path} · POST /api/setup/bundle/export {path}. Native file pickers come from the pywebview JS bridge.

## Daily highlights and topics (backend/app/content/)
- `scripts/shortlist_highlights.py`: candidates = non-repealed, 40–350 words, not a definitions section or schedule, contains
  right/duty markers (entitled, shall not, may not, right to, offence, without charge, within N days); balanced across Acts →
  data/highlights/candidates.json (chunk ids + titles only).
- `highlights.yaml` (repo, reviewed by a human): [{chunk_id, chunk_sha, topic, blurb:{en, sw}, status:
  unreviewed|approved|rejected}]. The builder picks ≥ 60 from candidates (selection only).
- `scripts/generate_highlight_blurbs.py` (needs Ollama; `@pytest.mark.real` test): Mistral, temperature 0.1, given ONLY that
  section: "Explain in 2 plain sentences what this section gives or requires; cite it." Validation, else discard: every
  citation verifies against the chunk (check_citations), every number/duration in the blurb appears in the chunk text,
  ≤ 60 words, no "you should" advice. Kiswahili via LanguageService (also unreviewed).
- Display: verbatim section always shown; unreviewed blurbs carry an "Unreviewed AI summary — check the text below" badge;
  rejected never shown; `highlights_show_unreviewed` (true) can hide them. A chunk_sha mismatch (corpus rebuilt) hides the entry.
- Rotation: approved first, then unreviewed; index = days since 2026-01-01 mod N, from the client's local date (no wall clock).
- `topics.yaml`: 7–10 life situations, each {slug, title {en,sw}, intro {en,sw}, chunk_ids[], example_questions[]}; builder
  drafts from domains.yaml + corpus titles, status needs_human_review (shown with a small "being reviewed" note).

## Desktop app (desktop/ + backend/app/desktop/)
- Launcher `desktop/launcher.py`: single-instance lock; pick a free 127.0.0.1 port; start uvicorn in a thread with
  settings.desktop_mode=true; open a pywebview window (WebView2 on Windows; GTK WebKit2 on Linux) at the local URL; JS bridge:
  pick_file, pick_folder, save_file, notify, open_external (allow-listed URLs only). If no webview backend is available, open
  the system browser and keep a small status window/console. Closing during a run asks to confirm.
- Data locations: platformdirs user data dir (`HakiAI`): app.db, feedback.jsonl, models/ (HF_HOME), ollama/ (managed mode),
  logs/. Read-only bundle resources: frontend/dist, data/processed/chunks.json, data/indexes/, content YAML. All paths come
  from config.py (`resource_dir`, `user_data_dir`), resolved from sys._MEIPASS when frozen.
- Ollama: use a running system Ollama if reachable; else "managed mode": download the official standalone release archive
  (pinned version + sha256 in config, filled by a human) into user data, run `ollama serve` as a child process with
  OLLAMA_HOST=127.0.0.1:<free port> and OLLAMA_MODELS in user data; stop it on exit. Model pull via Ollama /api/pull with progress.
- HF models: huggingface_hub snapshot_download with progress callback, resumable; verified by loading offline.
- Offline bundle (USB): folder with manifest.json (versions, sha256 per file), HF snapshots, Ollama model manifest + blobs, and
  optionally the Ollama archive; export from a set-up machine, import on another; verify checksums before copying.
- Packaging: PyInstaller onedir spec (`desktop/hakiai.spec`, torch CPU, excludes tests/eval/dev deps); Windows: Inno Setup
  per-user install (no admin), Start-menu entry, uninstaller asks whether to keep user data; Linux: AppImage + .deb
  (declares libwebkit2gtk-4.1-0 / gir1.2-webkit2-4.1). `desktop/selftest`: frozen binary `--self-test` runs with fake backends,
  hits /api/health and one query, exits 0. CI matrix (ubuntu-22.04, windows-2022) builds and self-tests artifacts.
- Unsigned builds trigger Windows SmartScreen; a code-signing certificate is an owner decision (HUMAN_TODO). No auto-update
  in v2 (would need hosting); "Check for updates" opens the releases page only if the owner configures a URL.

## Quality-of-life features (beyond the brief; each lives in a milestone below)
Background answers with notification and honest ETA (measured tokens/s stored per device) · follow-up questions · matters
(case folders) · letter workspace with profile autofill, versions and print · bookmarks, notes, recent reads · clickable
cross-references and "cited by" in the reader · "Ask about this section" · command palette and keyboard shortcuts (?, /,
Ctrl+K, Ctrl+Enter, g h / g l / g b) · guest and private modes, auto-lock, export/delete my data · text size, high contrast,
reduce motion, dark mode · read aloud via OS voices where speechSynthesis exists (hidden otherwise) · life-situation guides
and glossary · first-run tour and a plain "How HakiAI works / its limits" page · USB offline bundle · copy citation.

## New config (config.py only; validators like v1)
app_db_path, argon2_time_cost (3) / argon2_memory_kib (65536) / argon2_parallelism (2) [tests use minimal values],
auth_session_ttl_s (43200), auto_lock_s (900), login_max_attempts (5), login_lockout_s (30), letter_versions_max (20),
followup_context_turns (1), background_runs (true), search_max_results (50), snippet_chars (240), highlights_path,
topics_path, highlights_show_unreviewed (true), desktop_mode (false), desktop_port (0 = random), resource_dir,
user_data_dir, ollama_managed_version / ollama_archive_url / ollama_archive_sha256 (null until a human fills them),
setup_bundle_manifest_version (1), allowed_hosts.

## New dependencies (pin exact versions at first use; record in PROGRESS and LICENSES.md)
Backend: argon2-cffi (MIT), cryptography (Apache-2.0/BSD), platformdirs (MIT), pywebview (BSD) [desktop extra],
pyinstaller (GPL-2.0 with bootloader exception; build-time only). Frontend: react-router, @radix-ui/* primitives,
lucide-react (ISC), @fontsource/* (OFL), @tanstack/react-query. Dev: @axe-core/playwright for a11y checks.

## Planned deviations (each recorded in DEVIATIONS.md by its milestone)
D22 encrypted persistent history (privacy rule; M13) · D23 follow-up context in retrieval and USER QUESTION (prompt §7.1;
M14) · D24 background runs survive disconnect for signed-in users (D16; M14) · D25 LLM-written highlight blurbs outside the
per-query RAG flow (M16) · D26 desktop runtime: random port, data dirs, managed Ollama, setup endpoints (M17).

## Testing rules (v1 rules plus)
Crypto/auth tests use cheap argon2 params and an injected clock; a test asserts that no plaintext question/answer/letter
ever appears in the SQLite file bytes. Setup/download code sits behind interfaces with fakes (no network in tests).
Frontend: vitest + Testing Library per component, Playwright e2e per user journey against HAKI_FAKE_BACKENDS=1 (sign up →
ask → background → notification → library → letter edit → export; browse → search → bookmark; guest flow; lock/unlock),
axe checks on every route with zero serious/critical violations, screenshots at 1280 and 375 px, light and dark.
