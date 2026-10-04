# Review prompt (fresh session, after each milestone — the reviewer did not write the code)

Review the last commit(s) against docs/ARCHITECTURE.md and CLAUDE.md hard rules. Report only real problems, most severe first:
spec deviations, untested branches, hidden network/model calls in tests, hard-coded config, legal-text fabrication risks, error handling gaps.
For each: file:line, failure scenario, minimal fix. Do not rewrite code and do not praise. If nothing is wrong, say so in one line.
