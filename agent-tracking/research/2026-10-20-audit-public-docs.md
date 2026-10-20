# Research — 2026-10-20-audit-public-docs

## Coverage checks (lead)

- Every `.md` under `docs/` is in the `mkdocs.yml` nav (none orphaned).
- Every route in `src/api/routes/*.py` (50) has its path mentioned under `docs/api/`.
- MCP server (`src/api/mcp_docs.py`) indexes 96 pages; tools `list_docs`, `get_doc`, `search_docs` respond.

## MCP search spot check (top 3 for integrator questions)

| Question | Top 3 | Right page in top 3? |
|---|---|---|
| how do I make an outbound call | api/mcp.md, api/calls/webhook.md, api/assistant/placeholders.md | No — `api/calls/trigger.md` / `getting-started/outbound-sip.md` missing |
| end call webhook payload | api/calls/webhook.md, … | Yes |
| tool webhook request format | api/tools/webhook.md, … | Yes |
| web call token react client | api/calls/passthrough.md, api/calls/web-call.md, getting-started/web-call.md | Yes (2nd) |
| inbound call context webhook | api/inbound-context-strategy/index.md, … | Yes |
| authentication api key | api/authentication.md, … | Yes |
| error response format | api/tools/webhook.md, api/calls/best-practices.md, api/analytics/by-time.md | No — `api/errors.md` missing |
| rate limit concurrency 503 | changelog.md, concepts/meeting-calls.md, concepts/call-lifecycle.md | Partly |
| how it works architecture | concepts/index.md, … | Yes |
| create assistant cascade example | api/assistant/create.md, concepts/cascade.md, … | Yes |

- MCP `instructions` (`src/api/mcp_docs.py:125-135`) still advertise "container deployment"; that content moved to `dev-docs/` today.

## Investigator results

(appended as they return)

### Assistant / tools / audio / auth / errors (investigator 1; lead spot-checked items 1, 3, 4)

All 7 create and 6 update example bodies pass `CreateAssistant` / `UpdateAssistant` offline.

High: (1) `create.md:322-348` shows FastAPI `{"detail": …}` error bodies; every error is the envelope `{"success":false,"message":…,"data":{"errors":[…]}}` (`src/api/server.py:79-129`). (2) `create.md:114` says unread ElevenLabs `voice_settings` are dropped; they are a 422. (3) `docs/api/errors.md:61` and the live error string at `src/core/model_support/capabilities.py:366` name `POST /assistant/attach-tools`, which does not exist (real: `POST /tool/attach/{assistant_id}`). (4) `tools/create.md:143` webhook timeout default 10; code 30 (`tool_builder.py:178`). (5) Status-code tables say 400 where schema errors are 422 (create, update, attach, detach, tools/create); 404 for an unowned `audio_id` and the attach/detach 400 collision are missing.

Medium: tool `url`/`value` documented as required but not validated (tool silently skipped at call start); Deepgram/OpenAI language fallback note wrong (`multi` / `detect_language`, not `en`); Cartesia STT language is ISO 639-1, default None, `ink-2` missing; `assistant/get.md` missing `duplex` and seven returned fields; `update.md:208` gemini→cascade example wrong; `errors.md:21` omits `data.errors` on 422.

Low: 12 cosmetic items (regex, defaults, length limits, missing response fields, ElevenLabs model list, audio 25 MB cap, 3xx tool replies).

Out-of-scope code observations: `/audio/upload` reads the whole file before the 25 MB check (`audio.py:47`); tool webhook `url` not validated (SSRF to internal addresses, `tool_builder.py:173`); PATCH on a deleted assistant/tool is allowed; `PATCH /tool/update` does not re-run `enforce_tool_change`.

### Calls / telephony / webhooks (investigator 2; lead spot-checked 1, 2 and the redirect issue)

High: (1) Web/text chat: docs say agent replies arrive on `lk.chat`; the SDK publishes agent replies and transcripts on `lk.transcription` (`TOPIC_TRANSCRIPTION`, `livekit/agents/types.py:81`; room_io output), `lk.chat` is input only — a client built from `docs/api/calls/web-call.md:63-72` receives nothing. (2) `getting-started/outbound-sip.md:15-21` and `end-to-end-example.md:66-72` send flat `trunk_address`/… fields; `CreateOutboundTrunk` requires a `trunk_config` object → 422 on the very first step. (3) `inbound/flow.md`, `inbound/index.md`, `inbound/manage.md` describe a `context` envelope for the context webhook reply; the code spreads any JSON object flat (the strategy index page is right). (4) Passthrough webhook documented for all outcomes incl. a Twilio example; only Exotel passthrough sends it. (5) `sip/list.md` response fields wrong (`trunk_type`, `trunk_created_at` not returned). (6) Inbound-context-strategy pages show 400 + `{"detail":…}`; actual 422 + envelope.

Medium: web-call response has no LiveKit URL and no client recipe (mic, remote audio, `startAudio`, agent identity); `text_only` rule wrong (cascade allowed; realtime and duplex rejected); web-call 503 and `data.agent_dispatch` undocumented; passthrough trunk not refused by `/call/outbound`; normalized number examples wrong (`08044319240`, not `918044319240`); context-webhook timeout is per phase, not total; end-call payload omits `usage.estimated_cost_usd`, `pricing_*`, `unpriced_model_usage`, and leaks `recording_egress_id`; webhook is unsigned and the docs do not say so; 422 missing from trigger/sip/inbound tables; best-practices status table wrong; `calls/flow.md:76,78` capacity and load-threshold numbers stale; passthrough `metadata` not stored on the record.

Low: 8 cosmetic items (duplex missing from `usage.mode`, backoff schedule, inconsistent example numbers, broken indentation, trunk id prefix, step numbering, room-name format).

Security observation: `src/core/agents/inbound_context.py:184` uses `follow_redirects=True`, which bypasses the write-time private-address check on the context webhook URL (SSRF via redirect).

### Analytics / reference / MCP readiness (investigator 3; lead verified 3, 4, 8, 21; rejected 24)

Clean: analytics/admin/health/mcp routes, auth, query params; `pricing.md` has every rate key; `models.md` has every id except three OpenAI STT ids; all factory defaults match; changelog top = 1.6.0.

High: (a) the `attach-tools` route in a live error string (same as investigator 1); (b) web-call clients cannot learn the LiveKit URL (same as investigator 2); (c) MCP `instructions` (`src/api/mcp_docs.py:126-129`) and `docs/api/mcp.md:11,243` still promise container/deployment content, which moved to `dev-docs/` today — a leftover of the split.

Medium: `GET /logs` `limit=0` returns everything and `page<=0` is a 500 (`src/api/routes/logs.py:15-21`); `errors.md` incomplete (no 202/403/409/503; lists 502/504 nobody raises) and unlinked; admin and analytics token pages miss cost/STT fields and schemas; `docs/features.md:300-330` stale (2 s polling, 65 % CPU, Docker/`deploy.sh` section, "architecture diagrams" — leftovers of the split); OpenAI STT ids missing from `models.md`; base URL, `/openapi.json` and Swagger `/docs` stated nowhere; end-call webhook unsigned and undocumented as such; rate limits documented nowhere.

Low: 9 items (analytics wording, `%Y-W%V` ISO-week bug, timestamp format, `user_email` in logs, 422 rows, ElevenLabs list, `gpt-transcribe` pricing basis, `/documentation` 307, index page mode summary).

Rejected: "AGENTS.md Definition of done still lists docs/architecture/cascade-pipeline.md" — `grep docs/architecture AGENTS.md` returns nothing.

MCP readiness (18 questions): right page in top 3 for 12; answerable from that page alone for 8. Unanswerable today: web call from React (no URL), retry a failed queue item, rate limits, base URL, OpenAPI, verifying the webhook.
