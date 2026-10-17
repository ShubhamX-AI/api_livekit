# Plan — 2026-10-17-audit-logging-traceability (review plan)

**Goal:** judge whether the logs in `src/` and the three entry points are leveled, worded,
structured and safe, and whether one call can be followed end to end through them.

**Success criteria:** every log statement in scope judged; a yes/no per call-path hop on
traceability with the gap named at `file:line`; HTML report, all severities, no code changed.

**Skills:** core-be-audit-code, core-be-coding-standards (yardstick).

## Steps

- [ ] 1. Logger infrastructure: `src/core/logger.py`, `src/core/config.py` LOG_* settings,
      the three entry points, `agent_run.py` worker log setup, Gunicorn/uvicorn log config in
      `src/api/server.py`.
- [ ] 2. Trace one outbound call: `src/api/routes/call.py` -> `outbound_dispatcher/dispatcher.py`
      -> `services/livekit/livekit_svc.py` -> `custom_sip_reach/{bridge,sip_client,rtp_bridge}.py`
      -> `core/agents/session.py` -> `session_lifecycle.py` -> end-call webhook. For each hop:
      which id is on the line (queue_id, room, call record id, SIP Call-ID), can it be joined to
      the previous hop.
- [ ] 3. Trace one inbound call: `inbound_listener.py` -> `inbound_bridge.py` ->
      `inbound_worker.py` -> worker session; plus web call and meeting call routes.
- [ ] 4. Fan out the per-statement review to three read-only investigator subagents
      (API routes + validation; worker `core/agents/**`; `services/**`). Checklist per
      statement: level right, message names the entity and outcome, context ids present,
      traceback on errors, no secrets/PII (phone numbers, keys, transcripts), no f-string
      cost in hot paths, no swallowed exceptions. I open every returned `file:line` before it
      enters the report.
- [ ] 5. Cross-cutting: logger naming (`app` vs `__name__`), duplicate/noisy lines in hot
      loops (RTP, audio), JSON field consistency, job_proc forwarding, log file in containers.
- [ ] 6. Write the self-contained HTML report (no external scripts) to
      `agent-tracking/reports/2026-10-17-audit-logging-traceability.html`; fresh-context reviewer
      pass; update INDEX.

## Not reviewed

`scripts/`, `tests/`, `docs/`; the production log pipeline (not in the repo).

## Verification

Each finding cites `file:line` that I opened myself; anything unverified is marked *suspected*.
