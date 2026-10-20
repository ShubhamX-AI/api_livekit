# Research — 2026-10-17-audit-logging-traceability

## Logging setup (baseline read)

- One shared module, `src/core/logger.py` (194 lines). `setup_logging()` installs a root
  handler: coloured text to stdout by default, JSON when `LOG_JSON_FORMAT=true`
  (`src/core/logger.py:132-137`), plus a rotating JSON file handler at `LOG_FILE`
  (default `app.log`, `src/core/config.py:31`).
- The only correlation field is `call_room`, stamped at record creation by a custom record
  factory (`src/core/logger.py:55-62`) from a ContextVar with a module-global fallback
  (`src/core/logger.py:22-25`).
- `set_room_context` is called in only three places: the worker entrypoint
  (`src/core/agents/session.py:293`), the inbound bridge (`inbound_bridge.py:281`,
  ContextVar only) and the inbound worker process (`inbound_worker.py:49`). The API server,
  the outbound dispatcher and the outbound Exotel bridge never set it — to be confirmed in the
  manual pass.
- Most modules import the shared `logger` named `"app"`; seven modules use
  `logging.getLogger(__name__)` instead (`utils.py`, `smtp_service.py`, `tool_builder.py`,
  `database.py`, `inbound_context.py`, plus `import logging` in `bridge.py` and
  `voice_features.py`). Two naming schemes means `logger` in the output does not identify the
  module consistently.

## Automated pass (before any change)

Scope: `src/`, `agent_run.py`, `server_run.py`, `sip_dispatcher_run.py`.

| Measure | Count | Command |
|---|---|---|
| Files that log | 46 (13,476 lines) | `grep -rlE "logger\.(…)"` |
| `logger.debug` / `info` / `warning` / `error` / `exception` / `critical` | 15 / 238 / 105 / 123 / 1 / 0 | grep per level |
| f-string log messages | 374 (AST; the first grep missed multi-line calls) | AST pass |
| `%`-style lazy messages | 11 | grep |
| `exc_info=` uses | 27 at call sites | AST pass |
| `extra=` uses | 0 (the 18 grep hits were pydantic `ConfigDict`) | AST pass |
| `print(` calls | 1 real (`src/core/agents/stt/lang.py:234`) | grep |
| Ruff `BLE001` blind except | 120 | `uvx ruff check … --select G,LOG,TRY400,TRY401,BLE001,S110,S112 --statistics` |
| Ruff `G004` f-string in logging | 20 (Ruff only recognises `logging.getLogger` loggers, so the grep count is the real one) | same |
| Ruff `S110` try/except/pass | 14 | same |
| Ruff `TRY400` `error` where `exception` belongs | 8 | same |

Early reading: 123 `logger.error` calls against 29 `exc_info` and one `logger.exception` means
most error lines carry no traceback. To be confirmed per call site.

## Open questions

- None blocking. Production log shipping (where JSON lines go, which fields are indexed) is not
  in the repo; the report will state what it assumes.

## Manual pass — infrastructure and call path (verified by me)

- **Bridge child processes and logging (verified by experiment).** Bridges run in
  `forkserver` children (`src/services/outbound_dispatcher/dispatcher.py:53-65`). No bridge
  module calls `setup_logging()`. A child only gets logging configured when the parent's
  `__main__` happens to call `setup_logging()` at module top level, because multiprocessing
  re-imports `__main__` in the child. `sip_dispatcher_run.py:19` does; Gunicorn's main does not.
  Probe (`child_log_probe.py` in the session scratchpad): with a top-level `setup_logging()` the
  child logs normally; without it the child's root has no handlers, `logger.info` is dropped, and
  `logger.warning` comes out bare (no timestamp, level, logger or `call_room`) via
  `logging.lastResort`, and never reaches `LOG_FILE`. So when the API process runs the dispatcher
  (`ENABLE_DISPATCHER=true`, the default and the `full` deployment), every bridge INFO line is lost.
- **Several processes write one rotating file.** `RotatingFileHandler` (`src/core/logger.py:139-145`)
  is opened by each Gunicorn worker (`GUNICORN_WORKERS: "4"`, `docker-compose.yml:18`, same
  `LOG_FILE: /app/logs/api.log`) and, per the point above, by every bridge child of the
  dispatcher. The stdlib handler is not multi-process safe: each process rotates on its own
  count, so lines are lost or land in the rotated file.
- **No HTTP access log and no request id.** Gunicorn is started without `--access-logfile`
  (`server_run.py:9-19`), and `uvicorn.access` is raised to WARNING (`src/core/logger.py:147`).
  No middleware assigns a request id (`src/api/server.py` has only CORS). A 500 logged by the
  generic handler (`src/api/server.py:128-135`) carries neither method, path nor caller.
- **Generic 500 handler logs the raw traceback unredacted** (`src/api/server.py:134-135`) while
  its own comment (`:137-139`) says the exception text can contain a submitted api_key; only the
  response body is passed through `redact_text`.
- **Client errors at ERROR.** Every 422 is `logger.error` (`src/api/server.py:102`).
- **Outbound id chain:** API logs `queue_id` (`src/api/routes/call.py:58-61`) -> dispatcher logs
  `queue_id -> room` once (`dispatcher.py:650-652`) -> all later dispatcher lines carry only
  `room=` in the text -> worker sets `call_room` (`src/core/agents/session.py:291-293`).
  Joinable, but only through text search and one line; `queue_id` never appears in the worker.
- **Inbound id chain:** SIP `call-id` on listener lines -> `call_id -> room` mapping logged once
  (`inbound_bridge.py:282`) -> `call_room` from then on. Joinable.
- **Worker:** the DB-connect failure at `session.py:283-286` is logged before
  `set_room_context`, so it has no `call_room`, and without a traceback.
- **PII:** caller and callee phone numbers and user email at INFO on every call
  (`call.py:21-22`, `:58-61`, `dispatcher.py:650-652`, `inbound_bridge.py:241`).

## API layer reviewer — verified by me

- **Security, out of scope:** `POST /auth/create-key` (`src/api/routes/auth.py:13-14`) has no
  `Depends(get_current_user)` and the router is mounted with no dependencies
  (`src/api/server.py:156`). Anyone who reaches the API can mint an `lvk_` key for a new email.
  Reported to the user immediately; belongs to a `core-be-audit-security` / fix task.
- **MongoDB credentials in logs:** `src/core/db/database.py:42` logs the full `MONGODB_URL` at
  INFO on every process start and every worker job; the URL carries user and password
  (`src/core/config.py:15-16`).
- Raw `str(e)` logged unredacted while the HTTP body is redacted: `assistant.py:129`,
  `auth.py:30` (a duplicate-key error text includes the `lvk_` key).

## Worker reviewer — verified by me

Line correction to my earlier note: `entrypoint` starts at `session.py:282`; the DB-connect
failure is `:285-288`, `set_room_context` `:293`, start line `:294`.

- Start line `session.py:294` carries room and assistant_id only; `ctx.job.id` is never logged;
  `queue_id` is not in the job metadata, so the worker cannot be joined to the queue item except
  through `room_name`.
- End line `session.py:1559` is logged right after `create_task(_flush_and_end_call…)`, before
  teardown runs, and only on the participant-disconnect path. Verified.
- Early returns after a single ERROR line (`:298-300`, `:889-894`): verified. The impact on the
  CallRecord (left non-terminal) is *suspected*; the dispatcher's silent-call guard
  (`dispatcher.py:347`) covers some of these for outbound Exotel only.
- Callee number at INFO: `session.py:342`. Webhook URL at INFO: `tool_builder.py:181`; tool
  args at DEBUG: `:182`.
- Swallowed: `session.py:1262-1263` (`call_answered` packet), `voice_features.py:85-86`,
  `:350-351` (filler loop), `tts/factory.py:217-218` (Sarvam keepalive at DEBUG).
- Dead handler: `session.py:1614-1620` — `create_task` cannot raise the coroutine's error.
- `call_room` reaches callbacks and plugin tasks through the global fallback: correct by design.
