# LiveKit Agent Service

FastAPI backend plus LiveKit worker for real-time voice assistants with `pipeline` and `realtime` modes.

## What This Project Does

- Manages assistants, tools, SIP trunks, API keys, and call workflows.
- Runs voice agents in LiveKit rooms.
- Supports web calls with both text (`lk.chat`) and voice input, plus an opt-in **text-only mode** (`text_only: true`) that disables mic/TTS/STT/recording for pure-chatbot use.
- Supports outbound calling and Exotel inbound routing.
- Queues outbound call requests and dispatches them in the background at a controlled rate.
- Supports assistant runtime modes:
  - `pipeline`: OpenAI realtime (STT+LLM) + separate TTS provider
  - `realtime`: Gemini realtime (STT+LLM+TTS in one model)
- Supports start greetings in both modes when `assistant_interaction_config.speaks_first=true`.
- Stores transcripts and call records in MongoDB.
- Sends post-call webhook notifications.
- Sends post-call webhook notifications with both actual and billable call duration.
- Writes activity logs for tool calls, inbound context lookup, and end-call webhook delivery.
- Tracks per-call LLM token usage and TTS character counts via SDK metrics.
- Provides analytics endpoints for call duration, volume, and usage monitoring.
- Super-admin endpoints for cross-tenant analytics and token usage visibility.
- Protects worker capacity by buffering outbound requests and limiting new job intake under higher CPU load.

## Provider Support

- Outbound calls: `twilio` and `exotel`.
- Inbound calls: `exotel` only.
- Twilio inbound is not implemented.

## Exotel Outbound Lifecycle

- Exotel outbound API calls are queued first and return `202 Accepted` with a `queue_id`.
- A background dispatcher starts with the API process and promotes queued calls into active LiveKit sessions when capacity is available.
- Final call outcomes are delivered through end-call webhook payloads (`completed`, `busy`, `no_answer`, `timeout`, `failed`, etc.).
- Exotel outbound recording starts only after the bridge signals `call_answered` and the worker confirms egress start.
- Exotel recordings are explicitly stopped on call end using the stored egress id.
- Exotel completed-call duration is measured from `answered_at` to `ended_at`.
- Trunk/provider mismatch is rejected at API level (`trunk_type` must match `call_service`).

## Outbound Queueing

- `POST /call/outbound` validates the assistant and trunk, inserts an `outbound_call_queue` record, and returns `202 Accepted`.
- `GET /call/queue/{queue_id}` returns queue state for the requesting user.
- Queue states are:
  - `pending`: waiting for dispatcher capacity
  - `dispatching`: reserved by dispatcher and being turned into a live call
  - `dispatched`: LiveKit room + provider dispatch created successfully
  - `failed`: permanently failed after retry exhaustion
- Current dispatcher defaults:
  - up to `12` concurrent active sessions (set by `MAX_CONCURRENT_JOBS`)
  - polls the queue every `2` seconds (fallback poll every `30s` when idle)
  - retries dispatch failures up to `3` times
- Active-session protection also uses the worker load threshold in `src/core/agents/session.py` so the worker stops accepting new jobs around `65%` CPU load.

## Passthrough Mode (Web ↔ SIP, No AI Agent)

Passthrough mode lets a human web user speak directly to a phone caller through SIP without any AI agent involved.

### How it works

1. Enable passthrough on a trunk: set `passthrough_mode: true` when creating the trunk via `POST /sip/create-outbound-trunk`.
2. Web client calls `POST /call/outbound_passthrough` with `trunk_id` and `to_number`.
3. API synchronously creates a LiveKit room and returns a `room_token` and `room_name` in the `202` response.
4. Web client connects to LiveKit using `room_token` and publishes mic audio.
5. The SIP call is dialled in the background (via the outbound dispatcher). Once answered, audio flows bidirectionally: web mic → SIP → mobile and mobile → SIP → web speaker.
6. No AI agent is dispatched. No STT/LLM/TTS runs.
7. Recording and end-of-call webhook (if `passthrough_webhook_url` is set on the trunk) are handled by the dispatcher monitor rather than session.py.

### Call error handling

All SIP error outcomes (busy, no-answer, timeout, rejection) are handled identically to normal outbound calls:
- `busy` — SIP 486 / 600
- `no_answer` — SIP 408 or RTP silence timeout
- `timeout` — SIP setup timeout (60 s)
- `failed` — any other SIP error or bridge crash

Use `GET /call/queue/{queue_id}` to poll queue state. Final call status is in the `CallRecord` (use analytics or direct DB query).

### Recording

Recording starts after SIP answers and stops when the bridge exits. The S3 URL is stored in `CallRecord.recording_path`. If `passthrough_webhook_url` is set on the trunk, a full call-details webhook (same shape as the AI call webhook) is POST'd on **all** terminal outcomes — completed, busy, no-answer, timeout, failed.

### Call logs

Use `GET /call/records?passthrough_only=true` to list all passthrough call records. Supports filtering by `call_status`, `to_number`, `start_date`, `end_date`, `limit`, `offset`. Each record includes `is_passthrough: true` so call type is always identifiable. Since passthrough calls have no assistant, they do not appear in `/analytics/calls/by-assistant`.

### Limitations

- No transcript is generated (no STT).
- Hold detection events are published to the LiveKit room but no one acts on them (no session.py).

## Hold Detection & Suppression

- Exotel calls: Hold is detected instantly via SIP re-INVITE (`a=sendonly` or `a=inactive` in SDP).
- When hold is detected, the agent enters hold mode:
  - Silence watchdog stops (no reprompts during hold music)
  - Filler word controller stops (no backchannel fillers)
  - In-progress agent speech is interrupted
  - Transcript processing is suppressed
- On resume, normal agent behavior is restored automatically.
- Twilio and other providers: Hold detection is not yet implemented — the agent may respond to hold music.

## Architecture

1. API service (`src/api/server.py`) exposes REST endpoints (multiple Gunicorn workers in production).
2. SIP dispatcher (`sip_dispatcher_run.py`) — dedicated process that owns the inbound SIP listener and outbound dispatcher loop. See `docs/architecture.md` for the single-container vs. multi-container deployment model.
3. Worker (`src/core/agents/session.py`) joins LiveKit rooms and runs the assistant.
4. MongoDB stores assistants, tools, trunks, queued outbound calls, call records, and logs.
5. LiveKit handles media transport and room orchestration.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- MongoDB
- LiveKit server (cloud or self-hosted)
- API keys for providers you use (OpenAI, Google Gemini, Cartesia/Sarvam/ElevenLabs/Mistral, LiveKit)

## Environment Variables

Create `.env` in the project root.

```ini
PORT=8000
BACKEND_URL=http://localhost:8000  # Worker callback URL for webhook routing

# Container role controls (default "true" keeps single-container / dev setups working)
ENABLE_SIP_LISTENER=true   # Set "false" on api container when sip_dispatcher container is used
ENABLE_DISPATCHER=true     # Set "false" on api container when sip_dispatcher container is used
GUNICORN_WORKERS=1
MAX_CONCURRENT_JOBS=12

MONGODB_URL=mongodb://admin:secretpassword@localhost:27017
DATABASE_NAME=livekit_db

LIVEKIT_URL=ws://127.0.0.1:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

OPENAI_API_KEY=<your-openai-api-key>
GOOGLE_API_KEY=<your-google-api-key>
CARTESIA_API_KEY=<optional>
SARVAM_API_KEY=<optional>
ELEVENLABS_API_KEY=<optional>
MISTRAL_API_KEY=<optional>

# Email (optional — needed for email tool)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<your-sendgrid-api-key>
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Your App Name

AWS_ACCESS_KEY_ID=<optional-for-recording-upload>
AWS_SECRET_ACCESS_KEY=<optional-for-recording-upload>
AWS_REGION=us-east-1
S3_BUCKET_NAME=<optional-for-recording-upload>
S3_RECORDINGS_PREFIX=recordings/

LOG_LEVEL=INFO
LOG_JSON_FORMAT=False
LOG_FILE=app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

## Run Locally

Install dependencies:

```bash
uv sync
```

Start API server (also starts SIP listener + outbound dispatcher by default):

```bash
uv run server_run.py
```

Start the dedicated SIP dispatcher process (optional, for multi-worker / production setups):

```bash
uv run sip_dispatcher_run.py
```

Start worker in another terminal:

```bash
uv run -m src.core.agents.session dev
```

Optional Docker flow:

```bash
docker compose --profile control --profile agent up --build
```

Dockerfile selection by deployment mode:

- `control` mode builds with `Dockerfile.control`
- `agent` mode builds with `Dockerfile.agent`
- `full` mode builds all services with the original `Dockerfile`
- role-specific dependency manifests:
  - `docker/requirements-control.txt`
  - `docker/requirements-agent.txt`

Production dual-host deployment (recommended):

```bash
# Server A (control plane): api + sip_dispatcher
./deploy.sh control

# Server B (capacity node): agent only
./deploy.sh agent

# Single host full stack using original Dockerfile
./deploy.sh full
```

Optional: if Server A has spare CPU, also run agent there:

```bash
docker compose --profile control --profile agent up -d --build
```

Suggested first capacity step:

- Set `MAX_CONCURRENT_JOBS=20` in production `.env`.
- Keep only one `sip_dispatcher` running across all servers.
- Keep Exotel SIP/RTP public IP variables (`EXOTEL_CUSTOMER_IP`, `EXOTEL_MEDIA_IP`) pinned to the control-plane server.

Run unit tests:

```bash
uv run python -m unittest discover -s tests -v
```

Backfill existing call records with billable minutes:

```bash
uv run python -m scripts.backfill_billable_duration_minutes
```

## Documentation

- MkDocs source lives in `docs/`.
- Build docs site:

```bash
mkdocs build --strict
```

- Serve docs locally:

```bash
mkdocs serve
```

## Webhook Contracts

Use these pages as the canonical payload contracts:

- Inbound context strategy webhook: `docs/api/inbound-context-strategy/index.md`
- Tool webhook payload and response handling: `docs/api/tools/webhook.md`
- End-call webhook payload: `docs/api/calls/webhook.md`

## API Areas

- `/auth`
- `/assistant`
- `/tool`
- `/sip`
- `/call`
- `/call/queue/{queue_id}`
- `/call/outbound_passthrough` — start a passthrough call (web ↔ SIP, no agent)
- `/call/records` — list call records with optional filters; `passthrough_only=true` for passthrough-only view
- `/inbound`
- `/inbound_context_strategy`
- `/logs`
- `/web_call/get_token` — supports `text_only: true` for chatbot mode (no audio, no recording; pipeline-mode assistants only)
- `/analytics` — per-user call analytics (dashboard, by-assistant, by-phone-number, by-time, by-service)
- `/admin` — super-admin cross-tenant analytics and token usage (requires `is_super_admin` flag)

## Assistant Modes

- `pipeline` mode (default):
  - Requires `assistant_tts_model` and `assistant_tts_config`
  - Uses OpenAI realtime for STT+LLM and separate configured TTS for speech output
  - `assistant_llm_config` is optional; if provided, only `assistant_llm_config.api_key` is used to override `OPENAI_API_KEY`
  - When `assistant_interaction_config.speaks_first=true`, the assistant sends the configured start instruction as the first response
- `realtime` mode:
  - Requires `assistant_llm_config`
  - Uses Gemini realtime for STT+LLM+TTS in one model
  - `assistant_llm_config.provider` defaults to `gemini`; `api_key` overrides `GOOGLE_API_KEY`
  - Ignores `assistant_tts_model` and `assistant_tts_config` at runtime
  - When `assistant_interaction_config.speaks_first=true`, the assistant also sends the configured start instruction as the first response through the realtime conversation path

Note: `assistant_start_instruction` is honored in realtime mode whenever `assistant_interaction_config.speaks_first` is enabled.

## Max Call Duration

Each assistant can cap its own call length via `assistant_interaction_config.max_call_duration_minutes` (minutes, must be `> 0`). When unset or `null`, the platform default of **30 minutes** is applied.

- When the limit is reached, the assistant speaks a brief farewell and the call is torn down gracefully — recording, transcripts, usage, MongoDB CallRecord and the end-of-call webhook all finalize cleanly.
- The terminating reason is reported as `call_end_reason = "max_duration_exceeded"` in the webhook payload and in the `CallRecord` document. Normal hang-ups report `"natural"`.
- Passthrough calls (no AI agent) are not affected — the limit only applies to assistant-driven sessions.

## Project Structure

```text
api_livekit/
├── README.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── docker/
│   ├── Dockerfile.control
│   ├── Dockerfile.agent
│   ├── requirements-control.txt
│   └── requirements-agent.txt
├── mkdocs.yml
├── server_run.py
├── sip_dispatcher_run.py
├── .agents/
│   ├── workflows/
│   └── skills/
├── assets/
│   └── audio/
├── docs/
├── tests/
├── src/
│   ├── api/
│   │   ├── dependencies/
│   │   ├── models/
│   │   ├── routes/
│   │   │   ├── analytics.py
│   │   │   └── admin.py
│   │   └── server.py
│   ├── core/
│   │   ├── agents/
│   │   │   ├── session.py              # entrypoint / orchestrator
│   │   │   ├── dynamic_assistant.py    # Agent class
│   │   │   ├── session_lifecycle.py    # CallReadinessGate, RecordingManager
│   │   │   ├── inbound_context.py      # caller context resolution
│   │   │   ├── voice_features.py       # SilenceWatchdog / Filler / Hold controllers
│   │   │   ├── tool_builder.py         # DB-backed function tool loader
│   │   │   ├── utils.py                # render_prompt
│   │   │   ├── stt/
│   │   │   │   ├── __init__.py
│   │   │   │   └── sarvam_parallel.py  # Sarvam Saras v3 parallel STT tap
│   │   │   └── tts/
│   │   │       ├── __init__.py
│   │   │       └── factory.py          # TTS factory + Sarvam WS keepalive
│   │   ├── db/
│   │   ├── config.py
│   │   └── logger.py
│   └── services/
│       ├── outbound_dispatcher.py
│       ├── elevenlabs/
│       ├── mistral/
│       ├── email/
│       ├── exotel/
│       │   └── custom_sip_reach/
│       │       ├── bridge.py
│       │       ├── rtp_bridge.py
│       │       ├── sip_client.py
│       │       └── inbound_listener.py
│       └── livekit/
└── scripts/ 
```
