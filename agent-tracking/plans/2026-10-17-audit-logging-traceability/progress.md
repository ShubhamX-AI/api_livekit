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

## 2026-10-17 — review executed

- Steps 1-3 done by me: logger setup, entry points, outbound and inbound id chains; bridge
  child-process logging settled with a forkserver probe.
- Step 4: three read-only reviewers (API, worker, services). Every cited `file:line` opened by
  me before inclusion.
- Step 6: fresh-context reviewer checked the draft report. Corrected: the `extra=` count (0,
  not 18), f-string count (374 by AST), `exc_info` count (27), L-01 entry function, L-02 example
  text, L-07 scope (silence and max-duration do log), L-09 (dup-key leaks the email, not the
  key), L-14 (body only on rejection), L-25 (no "0 call(s)" every tick).
- Report: `agent-tracking/reports/2026-10-17-audit-logging-traceability.html` (self-contained,
  no scripts). No source changed by the audit.
