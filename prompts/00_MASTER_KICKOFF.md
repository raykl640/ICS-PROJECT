# Master kickoff prompt (paste ONCE into a fresh Claude Code session, in plan mode: Shift+Tab twice)

You are the sole engineer building HakiAI end to end. Read CLAUDE.md, docs/ARCHITECTURE.md and docs/BUILD_PLAN.md only.

Before writing any code, produce a short plan (max 40 lines) covering:
1. The exact directory tree and every public function/class signature for milestones M0–M7 (names, args, return types).
2. The interface + Fake for each heavy dependency (Embedder, CrossEncoder, LLMClient, Translator).
3. The pinned versions for requirements.txt (check they are mutually compatible).
4. Any ambiguity or contradiction in the docs and the default you propose for it.
5. Anything you will need from me (statute PDFs, hardware facts, decisions) listed up front so I can supply it now.

Do not implement anything yet. Save the approved plan to docs/DESIGN.md. Later sessions will read it instead of re-deriving it.
