# How to run this

0. Put the statute PDFs in data/raw_pdfs/. `git init`, commit this kit.
1. Interactive route (recommended for M0–M1, M8): `claude` -> paste prompts/00_MASTER_KICKOFF.md in plan mode -> approve -> /clear.
2. For each milestone: /clear, paste MILESTONE_TEMPLATE.md with {MX} filled + that milestone's lines from MILESTONE_NOTES.md.
3. After each milestone: new session, paste REVIEW.md, fix findings, commit.
4. Human gates: after M1 (inspect chunks) and before M9 (write ground truth).
5. Autopilot route for M2–M7 once M1 is approved: `./scripts/autopilot.sh M2 M3 M4 M5 M6 M7`, then review commits.
6. Run the real Ollama/model smoke test yourself on your laptop after M7 (scripts/smoke.py, which Claude writes in M7).
