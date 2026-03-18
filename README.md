# LiveKit Agent Service

FastAPI backend and LiveKit worker for running real-time voice assistants with OpenAI Realtime, Cartesia, Sarvam, and ElevenLabs.

## What It Does

- **Real-time AI Agents**: Powered by OpenAI Realtime API (GPT-4o) and Cartesia/Sarvam/ElevenLabs TTS.
- **SIP Support**: Create and manage SIP outbound trunks (Twilio/Exotel) for telephony integration.
- **Outbound Calls**: Trigger programmatic outbound calls to phone numbers (currently supporting Twilio).
- **Inbound Number Routing**: Assign Exotel inbound numbers to assistants and route inbound calls from database mappings.
- **Dynamic Assistants**: Create and configure assistants with custom prompts, typed TTS configuration (Cartesia/Sarvam/ElevenLabs), and start instructions.
- **Custom Tools**: Extend assistant capabilities with custom tools (Webhooks, Static Responses) that can be attached/detached dynamically.
- **Call Recording**: Automatic call recording with LiveKit Egress to AWS S3.
- **Transcripts**: Real-time transcription storage in MongoDB.
- **Webhooks**: Automatic webhook notifications for call completion with detailed analytics.
- **Activity Logs**: Per-user activity logs for tool calls and post-call webhooks, queryable via API.
- **Secure API**: API Key authentication for all management endpoints.

## Main Features

- **Framework**: FastAPI (Python 3.12+)
- **Real-time Communication**: LiveKit
- **Database**: MongoDB (with Beanie ODM)
- **AI/LLM**: OpenAI Realtime API
- **TTS**: Cartesia (Sonic-3), Sarvam (Bulbul:v3) & ElevenLabs (eleven_v3)
- **Deployment**: Docker & Docker Compose

## Tech Stack

1. **API Service**: Manages resources (Assistants, API Keys, Trunks) and triggers calls.
2. **Agent Worker**: Connects to LiveKit rooms to handle AI logic (STT, LLM, TTS).
3. **LiveKit Server**: Handles real-time audio/video transport.
4. **MongoDB**: Stores configuration (assistants, tools), call records, transcripts, and activity logs.
5. **Webhooks**: Pushes call data to external services upon completion. All outbound webhook calls are recorded as activity logs.

## Requirements

- Docker & Docker Compose
- LiveKit Server (Cloud or Self-hosted)
- MongoDB Instance
- API Keys:
  - OpenAI API Key
  - Cartesia API Key
  - Sarvam API Key
  - ElevenLabs API Key
  - LiveKit API Key & Secret
  - AWS S3 Credentials (for recordings)

## Environment Variables

Create a `.env` file in the project root.

```ini
PORT=8000
BACKEND_URL=http://localhost:8000

MONGODB_URL=mongodb://admin:secretpassword@localhost:27017
DATABASE_NAME=livekit_db

LIVEKIT_URL=wss://<your-livekit-domain>
LIVEKIT_API_KEY=<your-livekit-api-key>
LIVEKIT_API_SECRET=<your-livekit-api-secret>

OPENAI_API_KEY=<your-openai-api-key>
CARTESIA_API_KEY=<your-cartesia-api-key>
SARVAM_API_KEY=<your-sarvam-api-key>
ELEVENLABS_API_KEY=<your-elevenlabs-api-key>

LOG_LEVEL=INFO
LOG_JSON_FORMAT=False
LOG_FILE=app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

   # --- AI Providers ---
   OPENAI_API_KEY=<your-openai-key>
   CARTESIA_API_KEY=<your-cartesia-key>
   SARVAM_API_KEY=<your-sarvam-key>
   ELEVENLABS_API_KEY=<your-elevenlabs-key>

AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_REGION=us-east-1
S3_BUCKET_NAME=<your-bucket-name>
S3_RECORDINGS_PREFIX=recordings/
```

## Run Locally

Install dependencies:

```bash
uv sync
```

Start the API server:

```bash
uv run server_run.py
```

Start the LiveKit worker in another terminal:

```bash
uv run -m src.core.agents.session dev
```

## 📁 Project Structure

```
api_livekit/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── server_run.py          # Entry point — starts API + agent worker
├── assets/
│   └── audio/             # Background audio files (WAV)
├── docs/                  # MkDocs source documentation (see also: MkDocs site output in `site/`)
├── scripts/               # Utility scripts (e.g., migration)
├── site/                  # MkDocs static site output (auto-generated, do not edit by hand)
├── src/
│   ├── api/               # REST API (FastAPI)
│   │   ├── server.py
│   │   ├── dependencies/  # Auth middleware
│   │   ├── models/        # Request/response schemas
│   │   └── routes/        # Endpoints: assistant, auth, call, inbound, logs, sip, tool, web_call
│   ├── core/
│   │   ├── config.py      # Settings loaded from .env
│   │   ├── logger.py
│   │   ├── agents/        # LiveKit agent logic
│   │   │   ├── session.py          # Agent entrypoint & lifecycle
│   │   │   ├── dynamic_assistant.py
│   │   │   ├── tool_builder.py
│   │   │   └── utils.py
│   │   └── db/            # MongoDB (Beanie ODM)
│   │       ├── database.py
│   │       └── db_schemas.py
│   └── services/
│       ├── elevenlabs/    # ElevenLabs TTS (non-streaming)
│       ├── email/         # SMTP email
│       ├── exotel/        # Custom SIP bridge for Exotel
│       └── livekit/       # LiveKit service helpers
└── output-recordings/     # Local recording output (dev)
```

## 🧩 Agent Logic

```bash
uv run python src/api/server.py
```

1. Connects to the LiveKit room.
2. Fetches the assistant configuration from MongoDB using the `assistant_id` (derived from room name).
3. Injects `metadata` values into the prompt and start instruction.
4. Loads and attaches configured tools (webhooks/static) to the assistant. Each webhook tool call writes an activity log to MongoDB.
5. Initializes OpenAI Realtime API and Cartesia/Sarvam TTS (based on typed configuration).
6. Listens for `transcription` events and saves them to MongoDB.
7. Triggers the `end_call` webhook upon participant disconnection. The webhook fire result (success/error) is also written as an activity log.

## 📊 Activity Logs

Users can query their own activity logs via the API to observe tool calls and webhook deliveries in real time.

| Endpoint | Auth | Description |
|---|---|---|
| `GET /logs` | Bearer | Fetch paginated activity logs for the authenticated user |
| `POST /web_call/get_token` | Bearer | Generate a LiveKit web call token (for browser clients) |

### Query parameters

| Param | Default | Description |
|---|---|---|
| `log_type` | — | Filter by `tool_call` or `end_call_webhook` |
| `assistant_id` | — | Filter to a specific assistant |
| `room_name` | — | Filter to a specific call |
| `page` | `1` | Page number |
| `limit` | `50` | Items per page (max 100) |

### Log types

| Type | When it fires |
|---|---|
| `tool_call` | Every time the agent calls a webhook tool — includes URL, arguments, response, latency |
| `end_call_webhook` | When post-call data is sent to `assistant_end_call_url` — includes URL, latency, success/error |

```bash
docker-compose up --build
```

## Assistant Voice Behavior Settings

Assistant create and update requests support these flags:

- `assistant_speaks_first`: assistant greets first or waits for the user.
- `assistant_filler_words`: assistant can produce short live filler phrases while the user is speaking.
- `assistant_silence_reprompts`: assistant reprompts after silence and can end the session after repeated silence.

These settings are stored on the assistant and applied in the worker at session startup.

## Inbound Number Routing

- **Note**: The inbound SIP listener is started automatically when the API boots (if `INBOUND_SIP_LISTEN=true`), ensuring the application actively listens for incoming SIP calls on the local `EXOTEL_CUSTOMER_SIP_PORT`.
- Each active inbound number maps to zero or one assistant, and routing looks up the normalized number globally.
- Active number reuse is blocked across all users until the existing mapping is deleted.
- `POST /inbound/assign` currently accepts only `service="exotel"`; Twilio remains in the schema for future support.
- `POST /inbound/detach/{inbound_id}` keeps the number in the user's list without an attached assistant.
- `DELETE /inbound/delete/{inbound_id}` marks the mapping inactive and makes the number reusable again.
- The Exotel inbound bridge sends `call_type`, `service`, `assistant_id`, `assistant_name`, `inbound_number`, and `caller_number` into the LiveKit dispatch metadata.

Detailed API docs are available in MkDocs under the `Inbound Calls` section.

## Key Runtime Flow

1. API receives assistant or call requests.
2. LiveKit dispatch starts a worker session for the room.
3. Worker loads the assistant from MongoDB.
4. Worker builds the prompt, tools, TTS, and session behavior.
5. Worker stores transcripts and sends end-of-call details when the room closes.

## API Routes

- `/auth`
- `/assistant`
- `/sip` (Outbound SIP trunks)
- `/call` (Trigger outbound calls)
- `/inbound` (Manage inbound number mappings)
- `/tool`
- `/web_call/get_token`
- `/logs`
- `/documentation`

## Project Structure

```text
api_livekit/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── server_run.py
├── assets/
├── docs/
├── src/
│   ├── api/
│   │   ├── dependencies/
│   │   ├── models/
│   │   ├── routes/
│   │   └── server.py
│   ├── core/
│   │   ├── agents/
│   │   ├── db/
│   │   ├── config.py
│   │   └── logger.py
│   └── services/
│       ├── elevenlabs/
│       ├── email/
│       ├── exotel/
│       └── livekit/
└── uv.lock
```

## Notes

- `/documentation` is served from the built MkDocs site when the `site/` directory exists.
- Assistant details endpoints expose the stored voice behavior settings.
- Outbound call metadata is still supported for prompt placeholder rendering.
