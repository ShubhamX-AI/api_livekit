# Research — 2026-10-20-debug-logging-p1-fixes

Source findings: `agent-tracking/reports/2026-10-17-audit-logging-traceability.html`, L-01,
L-02, L-03, L-05, L-06, L-09. Each was re-read at its `file:line` on 2026-10-20; none had been
fixed in the meantime (`git status src` clean, `git log -- src` has no logging commit since the
audit).

## Baseline

| Check | Command | Result |
|---|---|---|
| Tests | `uv run python -m unittest discover -s tests` | 646 tests, OK |
| Lint (files to touch) | `uvx ruff check --output-format concise <files>` | 67 pre-existing errors: dispatcher.py 26, inbound_listener.py 9, inbound_worker.py 8, bridge.py 7, keys.py 11, server.py 2, sip_dispatcher_run.py 2, database.py 1, logger.py 1. The target is "no new ones", not zero. |
| Logging tests | `grep -l setup_logging tests/*` | none exist; `tests/test_logging.py` will be new |

## Current state per finding

- **L-01 / L-02.** `_bridge_subprocess_entry` (`src/services/exotel/custom_sip_reach/bridge.py:378-398`)
  and `inbound_bridge_subprocess_entry` (`inbound_worker.py:169`) never call `setup_logging()`.
  Children are launched from the forkserver context (`dispatcher.py:53-65`). Outbound
  `run_bridge` never calls `set_room_context`; inbound does (`inbound_worker.py:49`).
  `setup_logging()` is idempotent (`src/core/logger.py:131`), so calling it in a child that was
  already configured by the `__main__` re-import of `sip_dispatcher_run.py:19` adds no second
  handler. The job_proc early return (`logger.py:150`) does not apply: bridge children are
  named `bridge-out-<number>` (`dispatcher.py:621`) or the forkserver default.
  Neither formatter prints a pid (`logger.py:74`, `:104-113`).
- **L-03.** `src/core/db/database.py:42` logs `settings.MONGODB_URL` in full. The failure line
  at `:65` logs the exception text, which pymongo may build from the URI's host but not its
  password; the L-09 filter covers it either way.
- **L-05.** `outbound_dispatcher_loop` (`dispatcher.py:794-818`): `_fail_stale_calls_on_startup()`,
  the first `_process_pending()`, and `_recover_stuck_dispatching()` / `_process_pending()`
  inside `while True` are outside any `try`. The task is created at `sip_dispatcher_run.py:29`
  and `src/api/server.py:58` and awaited only at shutdown, so its exception is never logged
  while the process runs.
- **L-06.** `ensure_inbound_server` (`inbound_listener.py:128-145`) catches every exception from
  `asyncio.start_server`, logs the message without a traceback, and returns. Called from
  `sip_dispatcher_run.py:26` and `src/api/server.py:54`. With `GUNICORN_WORKERS>1` and the
  listener enabled, every worker after the first fails with EADDRINUSE and today survives; the
  production compose file sets `ENABLE_SIP_LISTENER=false` for the API (`docker-compose.yml:16`),
  and the `sip_dispatcher` service has `restart: unless-stopped`.
- **L-09.** Seven call sites log `{e}` raw (`assistant.py:129`, `auth.py:30`, `tool.py:43`,
  `sip.py:43`, `:74`, `inbound_context_strategy.py:65`) and the 500 handler logs the traceback
  (`server.py:134-135`). HTTP bodies go through `redact_text` (`src/core/providers/keys.py:167`).

## The hazard in reusing `redact_text` for logs

`redact_text` ends with `_LONG_TOKEN = [A-Za-z0-9_\-]{32,}` (`keys.py:24`). That pattern also
matches every id the logs are traced by:

| Id | Shape | Source |
|---|---|---|
| `queue_id` | 32 hex | `db_schemas.py:311` (`uuid4().hex`) |
| `assistant_id`, `tool_id`, `strategy_id`, `audio_id`, `inbound_id` | 36-char UUID | `assistant.py:80` and siblings |
| SIP Call-ID (`bridge_call_id`) | 36-char UUID | `dispatcher.py:611`, `sip_client.py:89` |
| SIP Via branch | `z9hG4bK-` + 32 hex | `sip_client.py:87` |

Running `redact_text` over every log line as-is would mask those ids and make the logs *less*
traceable than today. The log filter therefore needs a log variant that leaves canonical UUIDs
and 32-char lowercase hex alone and keeps every other rule (vendor key prefixes, `Bearer`,
labelled `api_key=` / `password:` assignments, other 32+ char tokens). The HTTP `redact_text`
stays as it is: masking an id in an error body is harmless, and changing it is out of scope.

Accepted residual risk: a provider key that is itself exactly UUID-shaped or 32 lowercase hex,
logged without a label, passes the log filter. Every key shape the platform takes today that
has a vendor prefix (`sk-`, `sk_`, `AIza`, …) or is longer (Deepgram's 40 hex) is still masked.

URL credentials (`scheme://user:pass@host`) are not matched by any `redact_text` rule; the log
variant adds one, so a connection string in an exception is masked too.

## How the filter must hook in

- `JsonFormatter.format` calls `self.formatException(record.exc_info)` directly
  (`logger.py:115-116`) and ignores `record.exc_text`, so a filter that only rewrites `exc_text`
  would not reach the JSON output. The formatter must prefer `record.exc_text`.
- `logging.Formatter.format` (used by `ColoredFormatter`) reuses `record.exc_text` when it is
  set, so pre-formatting and redacting it in the filter covers the text output.
- The filter goes on each handler that `setup_logging` adds. Records from LiveKit job
  processes are forwarded and re-emitted by the parent's handlers, so they are covered there.
- Third-party handlers (Gunicorn's own error log) are not covered; noted, not in scope.

## Open questions

None left; L-06 and L-09 were decided by the user (see `scope.md`).
