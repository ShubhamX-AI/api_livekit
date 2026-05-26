# Platform Feature List

Complete inventory of what this platform provides.

---

## 1. Voice AI Assistants

- **Pipeline mode** — OpenAI Realtime handles STT + LLM; a separate TTS provider synthesises speech output
- **Realtime mode** — Google Gemini Realtime handles STT + LLM + TTS in a single model; no external TTS required
- **Configurable system prompt** — full control over assistant persona, instructions, and behavior
- **Dynamic prompt placeholders** — embed call metadata (`{{caller_number}}`, `{{assistant_name}}`, etc.) and caller-fetched CRM data (`{{context.*}}`) directly in prompts via Mustache templates
- **Speaks-first / wait-for-caller** — toggle whether the assistant greets first or waits for the caller to speak
- **Configurable start instruction** — separate greeting/opening line, independent of the main system prompt
- **Max call duration cap** — per-assistant hard ceiling (minutes); assistant speaks a farewell and tears down cleanly when reached; defaults to 30 minutes platform-wide
- **End-call tool** — assistant can trigger call termination on a configurable phrase and deliver a final message
- **Assistant CRUD** — create, read, update, delete, and list assistants via REST API

---

## 2. TTS Providers

Four synthesis providers supported in pipeline mode:

| Provider | Notes |
|---|---|
| **Cartesia** | `sonic-3` model; voice selected by `voice_id` |
| **Sarvam** | `bulbul:v3`; Indian language support; configurable `target_language_code` and `speaker` |
| **ElevenLabs** | Non-streaming v3 path; voice and stability configurable |
| **Mistral** | Mistral TTS integration |

- Per-assistant TTS config; API key override per assistant
- TTS humanization prompting guides for all three major providers (Sarvam, Cartesia, ElevenLabs) included in documentation

---

## 3. STT / Speech Recognition

- **Sarvam Saras v3 parallel STT** — secondary STT tap running in parallel for enhanced multilingual transcription
- **OpenAI Realtime STT** — default in pipeline mode via OpenAI's half-cascade path
- Per-call `user_stt_provider` toggle: `sarvam` or `openai`
- Phone vs. web noise-reduction branching: `far_field` (G.711/PSTN) vs. `near_field` (browser mic) sent to OpenAI Realtime

---

## 4. Outbound Calls

- **AI-agent outbound call** — queue a call to any phone number; an AI assistant handles the conversation end-to-end
- **Async queue model** — `POST /call/outbound` returns `202 Accepted` with a `queue_id` immediately; the call is placed when capacity is available
- **Queue status polling** — `GET /call/queue/{queue_id}` returns current state: `pending → dispatching → dispatched → failed`
- **Retry on failure** — up to 3 dispatch attempts before permanent failure
- **End-call webhook** — configurable POST notification on call completion with full payload: duration, transcript summary, status (`completed`, `busy`, `no_answer`, `timeout`, `failed`), `call_end_reason` (`natural` or `max_duration_exceeded`), billable minutes, recording URL
- **Provider support**: Twilio (LiveKit-managed SIP), Exotel (custom SIP bridge)

---

## 5. Passthrough Calls (Human Agent, No AI)

- Web user speaks directly to a phone caller over SIP — no STT, LLM, or TTS
- `POST /call/outbound_passthrough` creates a LiveKit room synchronously and returns a `room_token` immediately
- SIP call dialled in background; audio routes bidirectionally once answered
- Recording starts after SIP answer; stored to S3
- End-of-call webhook on all terminal outcomes when `passthrough_webhook_url` is set on the trunk
- Call records tagged `is_passthrough: true`; filterable via `GET /call/records?passthrough_only=true`
- Supports filtering by `call_status`, `to_number`, `start_date`, `end_date`, `limit`, `offset`

---

## 6. Inbound Calls

- **Number-to-assistant mapping** — link any inbound phone number to an assistant; incoming calls route automatically
- **Inbound via Exotel** — custom SIP bridge handles inbound SIP signalling and RTP
- Inbound call records, transcripts, and webhooks handled identically to outbound

---

## 7. Inbound Context Strategies

- **Pre-call CRM/data fetch** — before the assistant speaks on an inbound call, the platform POSTs to your webhook with caller metadata
- Response `context` object injected into prompt templates as `{{context.<key>}}`
- Strategy types: `webhook` (POST to your endpoint, expects `{"context": {...}}`)
- Non-blocking by design — lookup failure never drops the call; assistant starts with default behavior
- Strategy CRUD: create, update, list, get, delete
- Sensitive header values masked (`****`) in list/details responses
- Lookup outcomes logged to activity logs

---

## 8. Web Calls (No SIP)

- Browser or mobile app joins a LiveKit room and speaks directly to the AI assistant
- `GET /web_call/get_token` issues a scoped LiveKit room token
- Supports both voice input and text chat (`lk.chat`)
- No SIP trunk required

---

## 9. Function Tools

- **Webhook tools** — during a conversation the assistant calls an HTTP POST to your endpoint; use for live data lookup or triggering external actions
- **Static-return tools** — assistant returns a fixed payload without HTTP; use for constant answers (support hours, policy text, etc.)
- Tool CRUD: create, read, update, delete, list
- Attach / detach tools to any assistant; an assistant can have multiple tools
- Tool webhook payload includes full call context (caller number, assistant ID, room name, conversation turn)

---

## 10. Audio Pipeline (Phone / PSTN)

- **G.711 decode** — PCMA (a-law) and PCMU (μ-law) decoding; non-G.711 payloads (DTMF/RFC 2833) discarded early
- **Stateful 2nd-order Butterworth high-pass at 80 Hz** — removes DC offset and sub-bass hum; state carried across RTP packet boundaries (no 50 Hz buzz artefact)
- **Polyphase FIR resampling** (`resample_poly` 8 kHz ↔ 48 kHz) — eliminates aliasing and metallic hiss vs. linear interpolation
- **`tanh` soft-clipping** — inbound gain + soft limiter preserves speech dynamics without harmonic distortion; outbound 0.7 scale + soft limiter keeps TTS within G.711 headroom
- **Outbound downsample** — 48 kHz TTS audio → 8 kHz G.711 with anti-aliasing FIR before encoding

---

## 11. Hold Detection & Suppression

- **Instant hold detection via SIP re-INVITE** — detects `a=sendonly` / `a=inactive` in SDP (Exotel only)
- On hold: silence watchdog stops, filler controller stops, any in-progress agent speech is interrupted, transcript processing suppressed
- On resume: normal agent behavior and watchdog restart automatically
- Hold/resume events published as LiveKit data packets to the room

---

## 12. Per-Utterance Input Guard

- **Fragment-loop prevention** — mutes caller audio source for the first N seconds (default 3 s) of each agent reply
- Prevents "Hello? Hello?" repeat barge-ins from fragmenting the agent's response
- Re-enables immediately when the agent finishes speaking (if before the window)
- Pipeline mode only (Gemini realtime owns its own audio pipeline)

---

## 13. Silence Watchdog & Reprompts

- Detects caller silence after configurable interval
- Sends up to a configurable max number of reprompt messages before ending the call
- Configurable per-assistant: `silence_reprompt_interval`, `silence_max_reprompts`
- Paused automatically during hold

---

## 14. Filler Words (Backchannel)

- Assistant emits natural filler sounds while thinking (e.g. "Hmm, let me check that…")
- Toggle per-assistant via `assistant_interaction_config.filler_words`
- Paused automatically during hold

---

## 15. Background Audio

- **Ambient office sound** — low-level background noise makes silences feel natural on phone calls
- **Thinking sound** — subtle typing sound while the LLM generates a reply
- Both independently toggleable per-assistant (`background_sound_enabled`, `thinking_sound_enabled`)

---

## 16. Transcripts & Call Records

- Full conversation transcripts stored in MongoDB per call
- `CallRecord` documents include: call status, duration, billable duration, recording URL, call end reason, provider, assistant used
- Queryable via `/call/records` with filters: `call_status`, `to_number`, `start_date`, `end_date`, `limit`, `offset`, `passthrough_only`

---

## 17. Call Recording

- Recordings started after call is answered (SIP answer confirmed)
- Recordings stopped on call end; uploaded to S3
- S3 URL stored in `CallRecord.recording_path`
- Per-assistant and per-trunk recording control

---

## 18. Usage & Billing Tracking

- Per-call LLM token usage tracked (input + output tokens) via SDK metrics
- Per-call TTS character counts tracked
- Billable duration (minutes) calculated from `answered_at` to `ended_at`
- `UsageRecord` documents stored per call in MongoDB
- Backfill script for historical records: `scripts/backfill_billable_duration_minutes.py`

---

## 19. Activity Logs

- Structured logs written for: tool calls, inbound context lookups, end-call webhook delivery
- Queryable via `/logs` endpoint
- Per-assistant call log view: `/assistant/{id}/logs`

---

## 20. Analytics (Per-User)

All analytics scoped to the authenticated user's API key.

| Endpoint | Data |
|---|---|
| **Dashboard** | Total calls, total duration, status breakdown (completed/busy/failed/etc.), period counts |
| **By Assistant** | Call count and duration per assistant |
| **By Phone Number** | Call count and duration per destination number |
| **By Time** | Time-series with day / week / month granularity |
| **By Service** | Breakdown by telephony provider (exotel / twilio / web) |

Date range filters on all endpoints.

---

## 21. Admin / Super-Admin Analytics

Requires `is_super_admin` flag on the API key. Cross-tenant visibility.

| Endpoint | Data |
|---|---|
| **Dashboard** | Platform-wide call totals, duration, status, active user count |
| **Calls by User** | Per-user call count and duration |
| **Calls by Phone Number** | Cross-tenant destination number breakdown |
| **Calls by Service** | Cross-tenant provider breakdown |
| **Token Summary** | Aggregate LLM tokens and TTS characters across platform |
| **Tokens by User** | Per-user token and TTS consumption |
| **Tokens by Assistant** | Per-assistant token and TTS consumption |

---

## 22. SIP Trunk Management

- Create, list, and deactivate outbound SIP trunks
- Provider-specific config: Twilio (LiveKit managed) and Exotel (custom bridge)
- `passthrough_mode` flag per trunk for human-agent calls
- `passthrough_webhook_url` per trunk for end-of-call notifications
- Trunk/provider mismatch rejected at API level

---

## 23. Authentication & API Keys

- API-key based auth (`Authorization: Bearer <key>`)
- Per-user key scoping — analytics and records always filter to key owner
- Super-admin keys for cross-tenant access
- Key CRUD managed via `/auth` endpoints

---

## 24. Outbound Dispatcher & Capacity Management

- Background dispatcher loop polls queue every 2 seconds; fallback 30 s poll when idle
- Configurable `MAX_CONCURRENT_JOBS` (default 12)
- CPU-load protection: worker stops accepting new jobs at ~65 % CPU
- Orphan reaper: stale `dispatching` records (> 5 min) reset to `pending` or failed
- Startup cleanup: `initiated`/`answered` call records from the previous server instance immediately failed

---

## 25. Deployment Flexibility

- **Single container** — API + SIP dispatcher + worker in one process (dev default)
- **Split-role containers** — dedicated `control` container (API + SIP dispatcher) and `agent` container (worker only)
- `ENABLE_SIP_LISTENER` / `ENABLE_DISPATCHER` env vars control which process runs what
- Docker Compose profiles: `control`, `agent`, `full`
- Role-specific dependency manifests: `docker/requirements-control.txt`, `docker/requirements-agent.txt`
- `deploy.sh` script for single-command production deploys per role

---

## 26. Email Tool (Optional)

- SMTP/SendGrid email sending available as a built-in assistant tool
- Configured via `SMTP_*` environment variables

---

## 27. API Documentation Site

- Full MkDocs Material docs site bundled with the API
- Served at `/documentation` directly from the running API server
- Includes getting-started guides, API reference, architecture diagrams, webhook payload contracts, and TTS humanization prompts
