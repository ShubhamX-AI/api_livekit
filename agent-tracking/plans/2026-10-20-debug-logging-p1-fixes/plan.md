# Plan — 2026-10-20-debug-logging-p1-fixes

**Status:** done (approved 2026-10-20 by Shubham Halder)

## Goal

Fix the six P1 findings of the 2026-10-17 logging audit (L-01, L-02, L-03, L-05, L-06, L-09)
without changing any other behaviour.

## Success criteria

- Every finding has a test in `tests/test_logging.py` that fails on today's code.
- `uv run python -m unittest discover -s tests` green (baseline 646 OK).
- No new ruff violations in touched files (baseline counts in research).
- Report at `agent-tracking/reports/2026-10-20-debug-logging-p1-fixes.html`, self-contained.

## Skills applied

core-be-workflow, core-be-debug (fix at the narrowest layer, regression test per bug),
core-be-coding-standards, core-be-write-tests.

## Steps

- [x] 1. **L-09 log redaction.** In `src/core/providers/keys.py` add `redact_log_text`: the
      same rules as `redact_text`, plus URL userinfo masking, minus masking of canonical UUIDs
      and 32-char lowercase hex. In `src/core/logger.py` add a `_RedactingFilter` on every
      handler `setup_logging` installs: it renders the message once, redacts it, clears
      `args`, and pre-formats and redacts `exc_text` / `stack_info`. `JsonFormatter` uses
      `exc_text` when set. Tests: key in a message, in args, in a traceback, in a Mongo URL;
      UUID, queue_id and Call-ID survive.
- [x] 2. **L-03.** `database.py:42` logs only host(s) and `DATABASE_NAME`, userinfo stripped
      with `urllib.parse.urlsplit`. Test: the logged line holds no password.
- [x] 3. **L-01 / L-02.** Both subprocess entry functions call `setup_logging()` first; the
      outbound one also `set_room_context(room_name)`. Add the pid to both formats
      (`%(process)d` in text, `"pid"` in JSON). Tests: calling each entry with the bridge
      coroutine patched configures the root logger and, for outbound, stamps `call_room`.
- [x] 4. **L-05.** In `outbound_dispatcher_loop`, the startup pass and each loop iteration run
      inside `try/except Exception` with `logger.error(..., exc_info=True)`, so a MongoDB error
      costs one iteration, not the dispatcher. `CancelledError` still propagates. Add a
      done-callback in `sip_dispatcher_run.py` and `src/api/server.py` that logs a dispatcher
      task that ended with an exception. Test: a raising `_recover_stuck_dispatching` is logged
      and the loop runs the next iteration.
- [x] 5. **L-06.** `ensure_inbound_server(*, required: bool = False)`: logs the bind failure
      with `exc_info=True`; re-raises when `required`. `sip_dispatcher_run.py` passes
      `required=True` (the container exits and Docker restarts it); `server.py` keeps the
      default, so the API keeps serving. Tests: both branches.
- [x] 6. Full suite, ruff on touched files, fresh-context reviewer subagent over the diff,
      code-simplicity-reviewer pass (repo memory asks for it after edits).
- [x] 7. Docs sync (troubleshooting note on the dispatcher exiting on bind failure; README
      only if something user-facing changed), report, INDEX `done`.

## Files expected to change

| Path | Change |
|------|--------|
| `src/core/providers/keys.py` | `redact_log_text` + URL-userinfo pattern |
| `src/core/logger.py` | redacting filter, pid in both formats, JSON uses `exc_text` |
| `src/core/db/database.py` | connect line without credentials |
| `src/services/exotel/custom_sip_reach/bridge.py` | `setup_logging` + `set_room_context` in the entry |
| `src/services/exotel/custom_sip_reach/inbound_worker.py` | `setup_logging` in the entry |
| `src/services/outbound_dispatcher/dispatcher.py` | guarded startup and loop body |
| `src/services/exotel/custom_sip_reach/inbound_listener.py` | traceback + `required` |
| `sip_dispatcher_run.py` | `required=True`, dispatcher done-callback |
| `src/api/server.py` | dispatcher done-callback |
| `tests/test_logging.py` | new |
| `docs/reference/troubleshooting.md` | dispatcher exits when port 5070 cannot be bound |

## Design notes

- **Why a log-only redactor.** `redact_text`'s 32+ char rule masks `queue_id`, every UUID id
  and the SIP Call-ID (research, "The hazard"). Applied to logs unchanged, it would destroy
  the traceability this task is meant to improve.
- **Cost.** Four regex passes per emitted record. Hot paths log once per call or once per 5 s
  (Sarvam DEBUG); RTP does not log per packet except on errors (L-20, out of scope).
- **Filter placement.** On handlers, not loggers: Python does not run parent-logger filters
  for propagated records (the same reason `_make_log_record` exists, `logger.py:55-58`).
- **Multi-writer log file.** Bridge children will now open `LOG_FILE` in the API-hosted
  dispatcher too, as they already do in the dedicated container. That is L-10 (several
  processes rotating one file), already known and out of scope.

## Risks and rollback

| Risk | Mitigation |
|---|---|
| Filter masks an id people grep for | UUID / 32-hex exemption with tests on each id shape |
| Filter raises inside logging | Python's handler error path prints and continues; the filter itself only uses `getMessage` and regex. Tested with bad `%` args. |
| Dispatcher now exits on bind failure where it used to limp on | User's decision; only `sip_dispatcher_run.py`, which Docker restarts |
| Loop swallowing a persistent error forever | Logged at ERROR with traceback every iteration (≤ every 30 s), visible, not silent |

Rollback: each step is one or two files; `git checkout -- <files>` for that step. No data,
schema or API change.

## Verification

```bash
uv run python -m unittest tests/test_logging.py -v
uv run python -m unittest discover -s tests          # expect 646 + new, OK
uvx ruff check --output-format concise <touched files>   # counts ≤ baseline
uv run mkdocs build --strict                          # if docs change
```
