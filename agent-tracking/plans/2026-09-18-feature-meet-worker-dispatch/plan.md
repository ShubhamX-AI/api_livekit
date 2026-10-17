# Plan 03 — Dispatching the connector as a LiveKit worker

This plan replaces the launch mechanism described in
[`01-meet-connector-service.md`](./01-meet-connector-service.md) and
[`02-api-livekit-integration.md`](./02-api-livekit-integration.md). Those two are implemented and
working code. The core-repository portion of this plan is now implemented; the connector repository
still needs the worker conversion described near the end of this document. Read this one before
touching either of the earlier plans again.

Everything about *what* a meeting call is — the call type, the capacity bucket, the wideband audio
tuning, the mixed-audio decision — is unchanged and stays exactly as plans 01 and 02 describe. The
only thing this plan changes is **how the connector is started and how it reports back**.

## The problem with what exists

The previous implementation in `src/services/meeting_connector/launcher.py` ran `docker run --rm -d` from inside the API process
to start a connector container per call, then keeps the container id on the `CallRecord` so it can
be killed later. The connector is configured entirely through the environment block that
`launch_connector` sets, because `ConnectorConfig.from_environment()` in the prototype is the only
input the connector has.

That machinery exists for one reason: the connector prototype is a one-shot script. It reads
environment variables at startup, joins one meeting, and exits. It cannot be told anything at
runtime, so the only way to give it a meeting URL is to start a fresh copy of it with that URL
already in its environment.

This is compensating in the API for a limitation of the connector. The cost shows up here:

- The API process needs access to a Docker daemon, which is a privilege it otherwise does not need
  and which makes the API harder to containerise (`launcher.py` would need the socket mounted).
- We hand-roll process lifecycle — launch timeout, kill, "already gone" handling —
  that LiveKit already does for the assistant worker.
- We invented a status callback (`POST /meeting_call/status`, `src/api/routes/meeting_call.py:161`)
  and a shared secret to authenticate it, purely so a process we started can tell us it started.
- Capacity is counted twice: once by our `MEETING` bucket
  (`src/services/outbound_dispatcher/dispatcher.py:78-90`) and, once the connector is a worker, again
  by LiveKit's own worker load.

Meanwhile the assistant in this same repo is started by LiveKit, given its room and its metadata by
LiveKit, and needs none of the above.

## The design

Make the connector a **second LiveKit agent worker**, registered under its own dispatch name, and
dispatch it into the same room as the assistant.

LiveKit supports several named agents in one room. From the agent-dispatch documentation: the
dispatch name "is a unique identifier for an agent. Explicit dispatch uses it to route jobs to the
right agent", and `CreateAgentDispatchRequest` takes `agent_name`, `room` and a `metadata` string of
up to 512 KiB. The agent server "boots a job subprocess which joins the room", one per job, which is
the isolation `docker run --rm` was providing by hand.

```
POST /meeting_call/join
  ├─ create_room()
  ├─ create_agent_dispatch(room, job_metadata,            agent_name="api-agent")
  └─ create_agent_dispatch(room, {"meeting_url": ..., },  agent_name="meet-connector")
                                          │
   assistant joins ───────────────────────┤── connector worker accepts the job,
   sets lk.publish_on_behalf              │   spawns its browser for that job,
                                          │   joins the meeting, publishes the
                                          │   mixed meeting audio into ctx.room
```

The connector receives its room through `ctx.room` and its meeting URL through `ctx.job.metadata`,
exactly as `entrypoint` in `src/core/agents/session.py` receives everything it needs today.

## Changes in this repository

### 1. `create_agent_dispatch` takes an agent name

`src/services/livekit/livekit_svc.py:70-81` hardcodes `agent_name="api-agent"` at `:77`. Add an
`agent_name: str = "api-agent"` parameter. Every existing caller keeps its current behaviour.

### 2. The route dispatches twice instead of launching a container

In `src/api/routes/meeting_call.py`, replace the `launch_connector(...)` call with a second
`create_agent_dispatch`, passing `agent_name=settings.MEETING_CONNECTOR_AGENT_NAME` and a metadata
dict carrying `meeting_url`, `platform` and `bot_display_name`.

`_abandon_room` stays and becomes more important, not less: if the second dispatch fails, the room
already holds an assistant.

### 3. Deletions

| Delete | Why |
|---|---|
| `src/services/meeting_connector/launcher.py` | LiveKit does the launching |
| `settings.MEETING_CONNECTOR_IMAGES` | there is no image for us to name |
| `settings.MEETING_CONNECTOR_STATUS_TOKEN` / `_STATUS_URL` | no callback to authenticate |
| `CallRecord.meeting_connector_container_id` | no container to track |
| `POST /meeting_call/status` and `MeetingConnectorStatus` | replaced — see change 4 |

`src/services/meeting_connector/platforms.py` **stays**. URL validation at the edge is still worth
doing, and `MEETING_URL_PATTERNS` is still the seam a second platform adds itself to. The package
keeps its name; it just holds one module instead of two.

### 4. Lifecycle without a callback route

Once the connector is a room participant, its arrival and departure are LiveKit events, and the
things we wanted the callback for have existing answers:

- **"the bot is waiting for admission"** — the connector publishes `{"event":"waiting"}` on the
  `meeting_connector_events` data topic.
- **"the bot got in"** — the connector publishes `{"event":"ready"}`. The assistant persists
  `meeting_connector_ready_at`, sets `lk.meeting_connector_status=ready`, marks the call answered,
  and only then sends its greeting. The participant attribute makes readiness recoverable if the
  data event predates the assistant's room connection.
- **"the bot failed to join"** — the connector publishes `{"event":"failed","detail":"..."}` or
  the assistant's readiness timeout expires. The assistant marks the call failed and ends the room.
- **"the meeting ended"** — the connector publishes `{"event":"ended"}` and the assistant's normal
  teardown calls `end_call(room_name)`.

These events are handled before `session.start()` can receive them. Connector state is separate from
`CallRecord.agent_ready_at`, which still means that the assistant session reached `session.start()`.
The core stores the connector state in `meeting_connector_status`,
`meeting_connector_status_reason`, `meeting_connector_ready_at`, and
`meeting_connector_ended_at`.

The honest trade: `call_status` moves to `answered` when the *assistant* is ready rather than when
the bot is admitted to the meeting, so a call sitting in a Google Meet waiting room reads as
answered. If that distinction matters for billing, add an `agent_ready`-style timestamp for the
connector instead of reinstating an HTTP route.

### 5. Capacity

`MAX_CONCURRENT_MEETING_CALLS` and the `MEETING` bucket stay. They are now a *business* cap — how
many meetings one customer's deployment will run — while LiveKit's `load_fnc` / `load_threshold` on
the connector worker is the *machine* cap, exactly as `agent_run.py:57-62` already does for the
assistant worker. Keeping both is deliberate; they answer different questions.

### 6. Settings

Replace the three deleted settings with one:

```python
self.MEETING_CONNECTOR_AGENT_NAME = os.getenv("MEETING_CONNECTOR_AGENT_NAME", "meet-connector")
```

## Changes in the connector repository

This is where the remaining work moves, and it is the larger half. The API-side migration is
complete, but the connector worker must still be implemented and deployed before meeting calls can
run end to end.

### 1. Become a worker

Add `livekit-agents` as a dependency and build an `AgentServer` the way `agent_run.py` does, with
`agent_name="meet-connector"`, a `load_fnc` that counts active jobs, and `load_threshold=1.0`.

### 2. Read the job instead of the environment

`ConnectorConfig.from_environment()` currently requires `MEETING_URL`, `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` and `LIVEKIT_ROOM`. After this change:

| Was | Becomes |
|---|---|
| `MEETING_URL` | `ctx.job.metadata["meeting_url"]` |
| `BOT_DISPLAY_NAME` | `ctx.job.metadata["bot_display_name"]` |
| `LIVEKIT_ROOM` | `ctx.room.name` |
| `LIVEKIT_SOURCE_PUBLISH_ON_BEHALF` | `ctx.room.name` |
| `LIVEKIT_URL` / `_API_KEY` / `_API_SECRET` | still environment — the worker needs them to register |
| `CONNECTOR_STATUS_URL` / `_TOKEN` | deleted |

The rest of `ConnectorConfig` — `audio_mode`, `ui_interaction_mode`, Chrome paths, timeouts — stays
environment-configured. Those are deployment settings, not per-call settings.

### 3. Publish through `ctx.room` rather than a new connection

`livekit_sync.py::_publish` opens its own `rtc.Room` and mints its own token. Inside a job the room
is already connected and handed over as `ctx.room`, so the inbound half becomes
`ctx.room.local_participant.publish_track(...)` on an `rtc.AudioSource`, and the connector no longer
needs `LIVEKIT_API_SECRET` for *that* purpose.

**It still needs the secret** for the outbound half: `source_browser_config` mints the hidden,
subscribe-only token that is injected into the browser page, and that has to be signed. So the
secret stays in the connector's environment — it just stops being used for the publisher side.

**Open question worth settling early:** whether the job's own participant should carry the meeting
audio, or whether the connector should still connect a second participant for it. A job participant
is `kind == AGENT`, and `AgentSession`'s participant linking skips agent participants — the docs note
`RoomIO` distinguishes AGENT, STANDARD and CONNECTOR kinds. If the assistant will not link to an
agent-kind participant, the meeting audio has to be published by a separate non-agent connection and
this saving does not apply. **Verify this before writing any of change 3.** It is the one thing in
this plan that could invalidate a piece of it.

### 4. One browser per job, cleanly torn down

The job subprocess boundary gives isolation for free, but Chrome, Xvfb and the WebSocket server are
started by `GoogleMeetChromeSession` and must be shut down in the job's shutdown callback rather
than in `cli.py`'s `finally`. A leaked Xvfb display or chromedriver survives the job process and
accumulates.

## How this differs from what is in the tree today

| | Today (plans 01 + 02, implemented) | This plan |
|---|---|---|
| Who starts the connector | our API, via `docker run` | LiveKit, via agent dispatch |
| How it learns the meeting | environment block on the container | `ctx.job.metadata` |
| How it learns the room | `LIVEKIT_ROOM` env var | `ctx.room` |
| How it finds the assistant | `lk.publish_on_behalf` attribute | unchanged |
| How it reports status | `POST /meeting_call/status` + shared secret | room data channel and job lifecycle |
| How it is stopped | `docker kill <container id>` | job ends |
| API needs Docker | yes | no |
| Meeting-specific code here | roughly 450 lines | roughly 120 |
| Connector deployment | image present on the API host | a worker deployment like `agent` |
| Connector complexity | one-shot script | LiveKit worker |

What does **not** change: `call_type="meeting"` / `call_service="google_meet"`, `src/core/call_types.py`,
the enum widening at `src/core/db/db_schemas.py:252-253`, the `MEETING` bucket, the three
`session.py` edits, `platforms.py`, the mixed-audio decision, and the public shape of
`POST /meeting_call/join`. A customer sees no difference at all.

## Why this was not the first design

Plans 01 and 02 took the connector prototype as a fixed input and built around it. That was the
wrong boundary to hold fixed: the prototype is ours to change, and changing it removes more code
than it adds. Recorded here so the same reasoning is not repeated for Zoom.

## Alternatives considered

- **Buy it.** LiveKit's LemonSlice avatar integration already joins Zoom, Google Meet, Teams and
  Webex through a managed relay that streams the meeting's mixed audio into the agent's STT and
  publishes the avatar back into the call. It is a paid third party and is avatar-shaped (it
  publishes video), so it does not fit an audio-only assistant without paying for a feature we do
  not want — but it should be a deliberate no, not an unexamined one.
- **A long-running connector HTTP service** that the API posts to. Simpler than `docker run`, but it
  is a second service to deploy, health-check and scale, and it reinvents what agent dispatch does.
- **No first-party option exists.** LiveKit's Connectors are telephony only — Twilio, WhatsApp, SIP.
  There is no Google Meet connector.

## Verification

1. **Two agents in one room.** Dispatch `api-agent` and a stub `meet-connector` into the same room
   by hand with `lk dispatch create`. Both must appear. No meeting involved.
2. **Settle the participant-kind question** from change 3 above: does `AgentSession` link to a track
   published by an agent-kind participant? Two clients, no meeting. If it does not, the connector
   publishes meeting audio from a separate non-agent connection and change 3 shrinks.
3. **Connector worker joins a real meeting** on dispatch, with the browser started from job metadata.
4. **Audio both ways**, which is the moment the feature exists.
5. `POST /meeting_call/join` end to end: one `CallRecord`, `initiated → answered → completed`, a
   `UsageRecord`, and the end-of-call webhook.
6. **Capacity.** `MAX_CONCURRENT_MEETING_CALLS` returns 503; a meeting call consumes no telephony slot.
7. `uv run python -m unittest discover -s tests`, `uvx ruff check` on touched paths,
   `uv run mkdocs build --strict`, `uv run python scripts/check_mermaid.py`.
