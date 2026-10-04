# Per-milestone prompt (fresh session each time: /clear first)

Do milestone {MX} from docs/BUILD_PLAN.md.
Read first: CLAUDE.md, docs/PROGRESS.md, docs/DESIGN.md, and only the source files this milestone touches.
Method: write failing tests first, implement until green, then run the full suite (`pytest backend/tests -q -x | tail -30`).
Scope: do exactly {MX}. Do not start the next milestone or refactor earlier ones unless a test proves a defect (then fix it and log it).
Finish: commit as `feat({MX}): <summary>`, append to docs/PROGRESS.md (done, decisions, open issues, next), then stop and reply with 5 lines max.
If you are blocked on something only I can provide, stop and say exactly what.
