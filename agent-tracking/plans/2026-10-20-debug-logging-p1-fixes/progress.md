# Progress — 2026-10-20-debug-logging-p1-fixes

## 2026-10-20 — scoped, researched, plan written

- Scope agreed with the user (`scope.md`): L-06 crashes only the dedicated dispatcher; L-09 is
  one global log filter; HTML report.
- Research found that `redact_text`'s 32+ char rule would mask `queue_id`, UUID ids and the SIP
  Call-ID if reused for logs; the plan uses a log-only variant (`research/…`, "The hazard").
- Baseline: 646 tests OK; 67 pre-existing ruff errors in the files to touch.
- `AGENTS.md` / `CLAUDE.md` already carry the pack registration; nothing changed there.
- Plan awaiting approval.

## 2026-10-20 — plan approved by the user ("Approve"); steps 1-3 done

- **Step 1 (L-09).** `src/core/providers/keys.py`: `redact_text` split into
  `_redact_labelled` + the long-token pass (behaviour unchanged, `tests/test_secret_redaction.py`
  green); new `redact_log_text` with `_URL_USERINFO` and `_TRACE_ID`. `src/core/logger.py`:
  `_RedactingFilter` on both handlers `setup_logging` adds; `JsonFormatter` prefers the
  redacted `exc_text`. A record whose `%`-args are broken is left untouched so the handler's
  `handleError` still reports it. Pydantic (needed by `keys.py`) is in both images through
  `beanie`, and `session.py` already imports `src.core.providers`.
- **Pid in both formats** (part of L-02, done in step 1's file): text `%(process)d`, JSON `"pid"`.
- **Step 2 (L-03).** `src/core/db/database.py`: the connect line logs `netloc` after the last
  `@` only. Test fails on the old code.
- **Step 3 (L-01 / L-02).** `setup_logging()` at the top of `_bridge_subprocess_entry`
  (`bridge.py`) and `inbound_bridge_subprocess_entry` (`inbound_worker.py`);
  `set_room_context(room_name)` in the outbound entry. Probe in the scratchpad: a forkserver
  child started from a `__main__` that never calls `setup_logging()` printed its INFO line as
  JSON with `pid` and `call_room=probe-room`; with `bridge.py` stashed the same probe printed
  nothing.
- `uv run python -m unittest tests/test_logging.py` → 14 OK.

## 2026-10-20 — steps 4-5 done; step 6 verification

- **Step 4 (L-05).** `outbound_dispatcher_loop`: the startup pass and each tick are wrapped in
  `try/except Exception` with `logger.error(..., exc_info=True)`; `CancelledError` (a
  `BaseException`) still propagates. New `log_dispatcher_exit` done-callback, exported from
  `src/services/outbound_dispatcher/__init__.py`, attached in `sip_dispatcher_run.py` and
  `src/api/server.py`; logs CRITICAL with the traceback, silent on cancel. Tests fail on the
  old code (4 errors).
- **Step 5 (L-06).** `ensure_inbound_server(*, required=False)`; bind failure logged with
  `exc_info=True`, re-raised when `required`. Only `sip_dispatcher_run.py` passes `True`.
  Tests fail on the old code.
- **Verification.** Full suite 666 OK (646 + 20 new). Ruff: no new violations versus the
  baseline in touched files; the three intentional broad catches carry `# noqa: BLE001` with
  a reason, matching `src/api/routes/health.py:34`. `tests/test_logging.py` is ruff-formatted
  and clean. `uv run mkdocs build --strict` OK; `scripts/check_mermaid.py` 21 checked, 0 broken.
- **Docs.** `docs/reference/troubleshooting.md`: new section "Outbound calls stay queued, or
  inbound calls are never answered" (the three new log lines, how to trace a bridge by
  `call_room` / `pid`, what the masking keeps readable). README unchanged: no env var,
  endpoint, script or folder changed.
- **Simplicity review** (code-simplicity-reviewer). Taken: drop the `stack_info` redaction
  (no caller uses it), drop `test_masks_message_args` (covered by the end-to-end handler
  test), comment why `_mask_unless_trace_id` subtracts ids instead of a fullmatch. Not taken:
  folding the two dispatcher `try` blocks into a helper (two short blocks; a helper adds a
  hop), and dropping the pid and HTTP-divergence tests (they pin behaviour this change adds).

## 2026-10-20 — fresh-context review, fixes applied

The reviewer subagent found no regression that could break a call, and confirmed
`redact_text` is unchanged and there is no import cycle. Its findings and what was done:

1. **Medium — any pure lowercase-hex token passed the log redactor** (40-hex Deepgram key,
   `sk_` + 48 hex, 64-hex signature), because 32-hex runs were stripped and the remainder was
   always under 32. Fixed: `_TRACE_ID` is anchored on hex boundaries, and a token is kept only
   if it contains an id and no 16+ char alphanumeric run is left (`_OPAQUE_RUN`). Negative
   tests added for all four shapes.
2. **Low — uppercase UUIDs were masked.** `_TRACE_ID` is now case-insensitive, so an Exotel
   Call-ID in upper case stays readable. Tested.
3. **Medium — LiveKit CLI's own root handler in the worker re-renders `exc_info`**
   (verified at `livekit/agents/cli/log.py`, `JsonFormatter.format`), so a worker-main
   traceback reached it unmasked. Fixed: the filter clears `exc_info` once the masked text is
   in `exc_text`; our `JsonFormatter` now reads `exc_text` (which also makes tracebacks
   forwarded from job processes appear in our JSON, where they were dropped before). Verified
   the text formatter still prints the masked traceback.
4. **Low — docstring said the second pass was a "no-op".** Reworded. Dict `msg` structure
   and `extra=` attributes are not redacted: noted below, not changed.
5. **Low — dispatcher comment overstated the retry.** Reworded.
6. **Low — `urlsplit` can raise on a bad IPv6 netloc.** Replaced with plain string splitting
   (authority after the scheme, host after the last `@`); checked with and without
   credentials, `+srv`, and a multi-host URL.
7. **Low — `redis://:pw@host` not masked.** User part of `_URL_USERINFO` is now optional.
   Tested.

Simplicity cuts applied at the same time: `stack_info` redaction removed,
`test_masks_message_args` removed. Suite 668 OK; ruff counts on touched files equal the
baseline.

## Out-of-scope observations

- Gunicorn's own error log handlers are not covered by the new filter.
- `extra=` attributes are written to JSON unredacted. Nothing in `src/` passes `extra=` today;
  the Sarvam plugin passes counters only.
- The filter turns a dict `msg` into its string form, so LiveKit's JSON formatter loses the
  dict structure for such records. No code in `src/` logs a dict.
- `redact_text` (HTTP bodies) still does not mask a short password inside a URL; left alone on
  purpose (scope).

## 2026-10-20 — report

- Report: `agent-tracking/reports/2026-10-20-debug-logging-p1-fixes.html` (self-contained, no scripts). INDEX row `done`.
- Nothing committed.
