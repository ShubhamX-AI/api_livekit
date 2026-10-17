# Progress — 2026-10-17-audit-logging-traceability

## 2026-10-17 — agent-tracking/ reorganised before the audit starts (user request)

The folder mixed the repo's numbered layout (`plan/`, `plan-tracking/`) with the core-be
layout. The user chose the core-be layout everywhere. Done with `git mv` so history follows:

- `plan/NN-*.md` -> `plans/<slug>/plan.md`; `plan-tracking/06-…` -> the Gemini task's
  `open-questions.md`; `plan-tracking/usage/usage-accounting.md` -> its own task folder.
- Research and reports renamed to their task's slug.
- `plan-tracking/usage/README.md` deleted: it described the retired layout.
- Every path reference rewritten: inside `agent-tracking/`, `AGENTS.md` and the comment at
  `src/api/mcp_docs.py:24` (comment only, no behaviour change).
- `AGENTS.md` "Agent working files" table rewritten for the new layout.
- `INDEX.md` lists all nine tasks with the old plan number, so prose saying "plan 03" resolves.
  Statuses of the older tasks were inferred from their own status lines.
- `demo-code/` left in place: root-owned and holds only empty directories.

Nothing committed.

## Out-of-scope observations

- `POST /auth/create-key` is unauthenticated (`src/api/routes/auth.py:13-14`). Told the user
  at once; not fixed.
