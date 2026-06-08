# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run API server (includes SIP listener + outbound dispatcher by default)
uv run server_run.py

# Run dedicated SIP dispatcher process (for multi-worker setups)
uv run sip_dispatcher_run.py

# Run LiveKit worker (separate terminal)
uv run -m src.core.agents.session dev

# Run tests
uv run python -m unittest discover -s tests -v

# Run single test file
uv run python -m unittest tests/test_session_lifecycle.py -v

# Lint
uv run ruff check .
uv run ruff format .

# Build docs
mkdocs build --strict

# Serve docs locally
mkdocs serve
```

## Architecture

Three concurrent processes form the runtime:

1. **API server** (`src/api/server.py`) — FastAPI app served by Gunicorn. Handles REST CRUD and dispatches calls via the outbound queue. On startup, optionally starts the SIP listener and outbound dispatcher (controlled by `ENABLE_SIP_LISTENER` / `ENABLE_DISPATCHER` env vars; both default `true` for dev).

2. **SIP dispatcher** (`sip_dispatcher_run.py`) — In production, a dedicated process that owns the Exotel inbound SIP listener (`src/services/exotel/custom_sip_reach/inbound_listener.py`) and the outbound dispatch loop (`src/services/outbound_dispatcher/dispatcher.py`). Only one instance should run across all servers.

3. **LiveKit worker** (`src/core/agents/session.py`) — Connects to LiveKit via the agents SDK. `entrypoint()` is the job handler; it resolves the assistant from MongoDB, builds TTS/STT, attaches voice features, and runs the session.

### Call flow (outbound)

`POST /call/outbound` → validates assistant + trunk (`trunk_type` must match `call_service`) → inserts `OutboundCallQueue` record → returns `202 Accepted` with `queue_id` → dispatcher polls every 2s (30s when idle) → creates LiveKit room + dispatches agent job → worker `entrypoint()` runs the session → end-of-call webhook + `CallRecord` finalized.

Queue states: `pending` → `dispatching` → `dispatched` (or `failed` after 3 retries). `GET /call/queue/{queue_id}` returns state.

### Concurrency / load control

- `MAX_CONCURRENT_JOBS` (default `12`) caps active sessions in the dispatcher (`src/core/config.py`).
- The LiveKit worker stops accepting new jobs around `65%` CPU load (load threshold in `src/core/agents/session.py`).
- Providers: outbound supports `twilio` + `exotel`; inbound supports `exotel` only (no Twilio inbound).

### Auth

REST routes require `Authorization: Bearer <api_key>` (keys are `lvk_`-prefixed, stored in `api_keys`). Dependency `get_current_user` validates; `get_super_admin` gates admin routes. See `src/api/dependencies/auth.py`.

### Key source locations

| Concern | Path |
|---|---|
| Agent session entrypoint | `src/core/agents/session.py` |
| Agent class (DynamicAssistant) | `src/core/agents/dynamic_assistant.py` |
| Session lifecycle (gate, recording) | `src/core/agents/session_lifecycle.py` |
| Voice features (silence watchdog, filler, hold) | `src/core/agents/voice_features.py` |
| TTS factory (cartesia/sarvam/elevenlabs/mistral) | `src/core/agents/tts/factory.py` |
| Sarvam parallel STT tap | `src/core/agents/stt/sarvam_parallel.py` |
| Tool loader (DB-backed function tools) | `src/core/agents/tool_builder.py` |
| Outbound dispatcher loop | `src/services/outbound_dispatcher/dispatcher.py` |
| Exotel SIP/RTP bridge | `src/services/exotel/custom_sip_reach/` |
| MongoDB schemas (Beanie ODM) | `src/core/db/db_schemas.py` |
| Settings / env config | `src/core/config.py` |
| API routes | `src/api/routes/` |

### Assistant modes

- **`pipeline`** (default): OpenAI realtime for STT+LLM, separate TTS provider. Requires `assistant_tts_model` + `assistant_tts_config`.
- **`realtime`**: Gemini realtime handles STT+LLM+TTS in one model. `assistant_tts_model` / `assistant_tts_config` are ignored at runtime.

TTS providers: `cartesia`, `sarvam`, `elevenlabs`, `mistral`. Per-provider config lives in `assistant_tts_config` dict on the `Assistant` document; factory is `src/core/agents/tts/factory.py`.

### MongoDB collections (Beanie documents)

`api_keys`, `assistants`, `audio_assets`, `outbound_sip`, `inbound_sip`, `tools`, `call_records`, `outbound_call_queue`, `inbound_context_strategies`, `usage_records`, `activity_logs` — all defined in `src/core/db/db_schemas.py`.

### Deployment modes

Controlled by `./deploy.sh <mode>` and Docker profiles:
- `control` — API + SIP dispatcher (`Dockerfile.control`, `docker/requirements-control.txt`)
- `agent` — LiveKit worker only (`Dockerfile.agent`, `docker/requirements-agent.txt`)
- `full` — all services on one host (`Dockerfile`)

In multi-host production: set `ENABLE_SIP_LISTENER=false` and `ENABLE_DISPATCHER=false` on the API container; run the dedicated `sip_dispatcher` container instead.

### Key env vars

All read in `src/core/config.py` (`Settings`). Beyond `ENABLE_SIP_LISTENER` / `ENABLE_DISPATCHER` / `MAX_CONCURRENT_JOBS`:
- DB: `MONGODB_URL`, `DATABASE_NAME`
- LiveKit: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- Providers: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `CARTESIA_API_KEY`, `SARVAM_API_KEY`, `ELEVENLABS_API_KEY`, `MISTRAL_API_KEY`
- Recordings (S3): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`, `S3_RECORDINGS_PREFIX`, `S3_GREETING_PREFIX`
- Webhooks/email: `BACKEND_URL`, `SMTP_*`, `FROM_EMAIL`
- Server: `PORT`, `GUNICORN_WORKERS`

## Runtime behaviors (see README.md for full detail)

- **Web call modes**: voice + text (`lk.chat`), plus opt-in `text_only: true` (disables mic/TTS/STT/recording for pure chatbot). `docs/api/calls/web-call.md`.
- **Passthrough mode**: human web user ↔ SIP phone caller, no AI agent. `docs/api/calls/passthrough.md`.
- **Greetings**: both modes greet first when `assistant_interaction_config.speaks_first=true`.
- **Audio library + prerecorded greeting**: reusable audio assets live in the `audio_assets` collection, managed via the `/audio` router (`upload` accepts any audio format, transcodes to WAV 48 kHz mono via PyAV/bundled-ffmpeg in `src/services/storage/audio_transcode.py`, enforces ≤ 30 s; `list`/`get`/`delete` soft-deletes). Assistants reference one by id through `assistant_greeting_audio = {enabled, audio_id}` (set via `/assistant/create` or `/assistant/update`). When enabled, the worker resolves `audio_id` → `AudioAsset` and plays the S3 WAV via `session.say(audio=...)` instead of model-generating the greeting — saves tokens in both modes. S3 access in `src/services/storage/s3_audio.py` (boto3, direct — not LiveKit egress). Any missing/inactive asset or download/decode failure falls back to the model greeting.
- **Billing**: webhook reports both actual and billable duration; Exotel completed duration measured `answered_at`→`ended_at`. `src/core/billing.py`.

## One-off scripts

`scripts/` holds migration/backfill jobs (e.g. `migrate_assistants.py`, `backfill_call_records.py`, `backfill_billable_duration_minutes.py`). Run with `uv run python scripts/<name>.py`.

## Webhook contracts

Canonical payload docs (not code):
- End-call webhook: `docs/api/calls/webhook.md`
- Tool webhook: `docs/api/tools/webhook.md`
- Inbound context strategy: `docs/api/inbound-context-strategy/index.md`
