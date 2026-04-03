# LiveKit Agent Service

FastAPI backend plus LiveKit worker for real-time voice assistants with `pipeline` and `realtime` modes.

## What This Project Does

- Manages assistants, tools, SIP trunks, API keys, and call workflows.
- Runs voice agents in LiveKit rooms.
- Supports web calls with both text (`lk.chat`) and voice input.
- Supports outbound calling and Exotel inbound routing.
- Supports assistant runtime modes:
  - `pipeline`: OpenAI realtime (STT+LLM) + separate TTS provider
  - `realtime`: Gemini realtime (STT+LLM+TTS in one model)
- Supports start greetings in both modes when `assistant_interaction_config.speaks_first=true`.
- Stores transcripts and call records in MongoDB.
- Sends post-call webhook notifications.
- Writes activity logs for tool calls, inbound context lookup, and end-call webhook delivery.
- Tracks per-call LLM token usage and TTS character counts via SDK metrics.
- Provides analytics endpoints for call duration, volume, and usage monitoring.
- Super-admin endpoints for cross-tenant analytics and token usage visibility.

## Provider Support

- Outbound calls: `twilio` and `exotel`.
- Inbound calls: `exotel` only.
- Twilio inbound is not implemented.

## Exotel Outbound Lifecycle

- Exotel outbound API calls return `202 Accepted` while SIP setup continues asynchronously.
- Final call outcomes are delivered through end-call webhook payloads (`completed`, `busy`, `no_answer`, `timeout`, `failed`, etc.).
- Exotel outbound recording starts only after the bridge signals `call_answered` and the worker confirms egress start.
- Exotel recordings are explicitly stopped on call end using the stored egress id.
- Exotel completed-call duration is measured from `answered_at` to `ended_at`.
- Trunk/provider mismatch is rejected at API level (`trunk_type` must match `call_service`).

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

1. API service (`src/api/server.py`) exposes REST endpoints.
2. Worker (`src/core/agents/session.py`) joins LiveKit rooms and runs the assistant.
3. MongoDB stores assistants, tools, trunks, call records, and logs.
4. LiveKit handles media transport and room orchestration.

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

Start API server:

```bash
uv run server_run.py
```

Start worker in another terminal:

```bash
uv run -m src.core.agents.session dev
```

Optional Docker flow:

```bash
docker-compose up --build
```

Run unit tests:

```bash
uv run python -m unittest discover -s tests -v
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
- `/inbound`
- `/inbound_context_strategy`
- `/logs`
- `/web_call/get_token`
- `/analytics` — per-user call analytics (dashboard, by-assistant, by-phone-number, by-time, by-service)
- `/admin` — super-admin cross-tenant analytics and token usage (requires `is_super_admin` flag)

## Assistant Modes

- `pipeline` mode (default):
  - Requires `assistant_tts_model` and `assistant_tts_config`
  - Uses OpenAI realtime for STT+LLM and separate configured TTS for speech output
  - When `assistant_interaction_config.speaks_first=true`, the assistant sends the configured start instruction as the first response
- `realtime` mode:
  - Requires `assistant_llm_config`
  - Uses Gemini realtime for STT+LLM+TTS in one model
  - Ignores `assistant_tts_model` and `assistant_tts_config` at runtime
  - When `assistant_interaction_config.speaks_first=true`, the assistant also sends the configured start instruction as the first response through the realtime conversation path

Note: `assistant_start_instruction` is honored in realtime mode whenever `assistant_interaction_config.speaks_first` is enabled.

## Project Structure

```text
api_livekit/
├── README.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── mkdocs.yml
├── server_run.py
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
│   │   │   ├── session.py
│   │   │   └── voice_features.py
│   │   ├── db/
│   │   ├── config.py
│   │   └── logger.py
│   └── services/
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
