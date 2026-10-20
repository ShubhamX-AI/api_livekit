# Scope — 2026-10-20-debug-logging-p1-fixes

- **Type:** debug (fix task planned from an audit's findings)
- **Requested by:** Shubham Halder (backend engineer)
- **Date:** 2026-10-20
- **Source:** `agent-tracking/reports/2026-10-17-audit-logging-traceability.html`, follow-up
  "Fix task, logging P1"

## Original request (verbatim)

The agent offered: "Want me to start the P1 logging fix task (L-01, L-02, L-03, L-09, L-05,
L-06)? That's a new fix task with its own plan for approval." The user answered:

> YEs Do it peroply in proeper structuer useign the skills na deverythign and dont breake anything

Interpreted as: "Yes. Do it properly, in the proper structure, using the skills and everything,
and don't break anything."

## Agreed scope

| Question | Answer |
|----------|--------|
| Target (paths / endpoints / diff) | Findings L-01, L-02, L-03, L-05, L-06, L-09 of the 2026-10-17 logging audit |
| Depth (quick / standard / deep) | standard: fix plus a regression test per finding |
| Out of scope | Every other finding (L-04, L-07, L-08, L-10–L-28) and the unrelated observations (`/auth/create-key`, SMTP timeout, etc.) |
| Constraints | No behaviour change beyond what each fix needs; no new dependencies; public API unchanged; nothing committed |
| Success criteria | Each finding fixed with a test that fails without the fix; full suite green; ruff clean on touched files |
| Report format (HTML / MD) | HTML, self-contained (no external scripts: it discusses secrets in logs) |
| Severity cut-off | n/a (fix task) |
| Type-specific answers | L-06: re-raise only in `sip_dispatcher_run.py`; inside the API process log the traceback and keep serving. L-09: one global redacting filter in `src/core/logger.py` |

## Assumptions confirmed with the user

- "Yes" to the offered P1 set means exactly those six findings.

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| L-06: on SIP bind failure, crash the process, or keep running with a traceback? | Crash the dedicated dispatcher only; the API process logs the traceback and keeps serving HTTP |
| L-09: one redacting logging filter, or redact at each call site? | Global log filter |
| Report format: HTML or Markdown? | HTML |
