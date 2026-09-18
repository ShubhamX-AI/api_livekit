# Plan 01 — The Attendee service

**Scope:** everything that runs outside this repository. What we host, what we switch off, how it
is configured, and the single API call this repository makes into it.

**Companion document:** [`02-api-livekit-integration.md`](02-api-livekit-integration.md) covers the
changes inside this repository. The two can be worked in parallel; the contract between them is the
`POST /api/v1/bots` body in [The one API call we make](#the-one-api-call-we-make) and the webhook
payload described in plan 02.

---

## Why Attendee at all

Google offers no first-party way to put a speaking bot into a Meet. The Meet Media API is
receive-only by design, its OAuth scopes all end in `.readonly`, and it is gated behind the
Developer Preview Program. The Add-ons SDK runs as browser JavaScript inside a human's Meet client
and has no audio access. The full source-by-source account is in
[`docs/research/google-meet-agents.md`](../docs/research/google-meet-agents.md).

That leaves one approach: a browser that joins the meeting the way a person does. We investigated
building our own with Playwright. It is entirely possible — roughly 200 lines for the join flow, an
in-page `getUserMedia` patch, and a WebSocket carrying PCM — but the ongoing cost is not the code.
It is tracking Google Meet's DOM, its admission flows, its error states, and its bot detection,
forever.

Reading `attendee-labs/attendee` settled it. The project already contains the exact bridge we were
about to write:

> Mirrors meeting participants into a LiveKit room. Each meeting participant is represented as its
> own LiveKit participant by opening a dedicated `rtc.Room` connection using a per-participant
> access token. Each synced participant publishes a single mono audio track, and the meeting
> participant's audio is captured into that track so that the LiveKit room reflects both the
> meeting roster and who is speaking.
>
> — `bots/bot_controller/livekit_room_sync_client.py`

The same client also streams a designated LiveKit participant's media *back into* the meeting. That
is both halves of our bridge, already written, and it is exposed through the public API as
`room_sync_settings` (`bots/serializers.py:1145-1191`).

## Why we do not extract the browser layer

The meeting-join layer is not small, and it is not portable:

| Component | Size |
|---|---|
| `bots/google_meet_bot_adapter/google_meet_chromedriver_payload.js` | 98 KB |
| `bots/google_meet_bot_adapter/google_meet_ui_methods.py` | 65 KB |
| `bots/web_bot_adapter/web_bot_adapter.py` | 67 KB |
| `bots/web_bot_adapter/shared_chromedriver_payload.js` | 34 KB |
| `bots/bot_controller/bot_controller.py` | 116 KB |
| `bots/google_meet_bot_adapter/mocap/*.json` | 2.5 MB |

That last row is recorded mouse-motion traces, replayed during the join so the cursor moves the way
a human's does. It is exactly the kind of accumulated, unglamorous work that makes the difference
between a bot that joins and a bot that gets blocked.

More decisively, the layer is coupled to Django. `livekit_room_sync_client.py:10` is
`from bots.models import ParticipantEventTypes`. Extracting the adapter means dragging `models.py`
and ninety-three migrations along with it. There is no clean seam.

So we take none of it. We run the project whole, as a sidecar, and disable what we do not use.

---

## What we run

Attendee is deployed from its own repository as a separate `docker-compose` stack, alongside but
not inside our own `docker-compose.yml` — it brings its own PostgreSQL and Redis, which have
nothing to do with our MongoDB.

Nothing is forked or vendored. Unused features are disabled by configuration, never by deletion:
deleting code we do not use would buy nothing and would put us on a permanent rebase against
upstream.

Services, derived from Attendee's `dev.docker-compose.yaml` and adapted for production:

| Service | Command | Why we need it |
|---|---|---|
| `attendee-app` | Django on port 8000 | Serves `POST /api/v1/bots`, the only endpoint we call |
| `attendee-worker` | `celery -A attendee worker` | Webhook delivery and cleanup tasks |
| `attendee-bot-launcher` | `celery -A attendee worker -Q bot_launcher_vm` | Required by our chosen launch method. `bots/launch_bot_utils.py:44-49` dispatches `run_bot_in_ephemeral_container` to exactly this queue name |
| `attendee-scheduler` | `python manage.py run_scheduler` | Runs the heartbeat-timeout and orphan cleanup commands. Without it, a crashed bot stays in `joining` forever and its slot never frees |
| `postgres` | `postgres:15.3-alpine` | Attendee's own database |
| `redis` | `redis:7-alpine` | Celery broker |

Deliberately **not** run:

- `attendee-webpage-streamer` — serves the `voice_agent_settings` webpage mode, where Attendee
  loads a URL in a container and treats that page's audio as the bot's microphone. That is a real
  alternative to room sync, but it puts a browser between our agent and the meeting for no benefit
  when our agent can simply be a LiveKit participant.
- The Kubernetes `bot_pod_creator` path — see the launch method decision below.
- Anything Zoom or Teams. Both are supported by the same `room_sync_settings` and are close to free
  to add later, but they are not this change.

## Bot launch method

`LAUNCH_BOT_METHOD=docker-compose-multi-host`.

`bots/launch_bot_utils.py:15-58` offers three:

- `kubernetes` — one pod per bot. Best isolation and autoscaling, but requires a cluster we do not
  have today.
- `docker-compose-multi-host` — an ephemeral Docker container per bot, launched from a Celery task
  on the `bot_launcher_vm` queue. Matches how we already deploy.
- Default (unset) — the bot runs inside the Celery worker process. Attendee's own README warns that
  co-locating bots this way makes "audio from separate meetings bleed together". Acceptable for a
  first smoke test, never for production.

One consequence to check before deploying: the launcher container needs to create sibling
containers, which normally means mounting the Docker socket. Whether that is acceptable on our host
is open item **V5** below.

## What we switch off

The principle is that this repository stays the source of truth for everything it already owns.
Attendee exists to get audio in and out of a Google Meet, and nothing else.

| Feature | How it is disabled | Why |
|---|---|---|
| Recording | Per-bot recording settings — confirm a no-recording configuration exists (open item V3) | `src/core/agents/session_lifecycle.py` already records to our S3 bucket |
| Transcription | Simply add no Deepgram, Gladia, AssemblyAI or Kyutai credential | Our STT already transcribes. A second transcript in a second database splits the truth for no gain |
| Signup | `DISABLE_SIGNUP=true`, after creating one admin user | Nothing external should be able to reach this service |
| Email | `DISABLE_EMAIL=true` | No transactional mail is needed |
| Billing | `CHARGE_CREDITS_FOR_BOTS=false` (the default) | Stripe credits are their product's billing, not ours |
| Calendar sync | Add no Google or Microsoft calendar connection | We trigger manually, per plan 02 |

Webhooks stay **on**. They are the only way our `CallRecord` learns that the bot actually got into
the meeting; see plan 02 for the mapping.

## Configuration

The full reference is Attendee's own `docs/environment-variables.md`. The variables that matter for
this deployment:

```bash
# Generated once by `python init_env.py`
DJANGO_SECRET_KEY=
CREDENTIALS_ENCRYPTION_KEY=

DATABASE_URL=postgresql://attendee:...@postgres:5432/attendee
REDIS_URL=redis://redis:6379/0
POSTGRES_SSL_REQUIRE=false
DJANGO_SSL_REQUIRE=false          # we terminate TLS ourselves
SITE_DOMAIN=<internal host>

LAUNCH_BOT_METHOD=docker-compose-multi-host

DISABLE_SIGNUP=true
DISABLE_EMAIL=true
REQUIRE_HTTPS_WEBHOOKS=false      # webhooks travel to our API over the internal network

# Required even with recording disabled
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_RECORDING_STORAGE_BUCKET_NAME=
```

`AWS_RECORDING_STORAGE_BUCKET_NAME` is documented as **Required**, so it must be set even when we
never record. Point it at a bucket or prefix with a one-day lifecycle rule so that anything written
by accident expires on its own.

### The LiveKit credential

One credential is added per Attendee project, of type `CredentialTypes.LIVEKIT = 13`
(`bots/models.py:2810`), holding:

```json
{"url": "...", "api_key": "...", "api_secret": "..."}
```

These are the same `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` already in our `.env`.
Attendee's room-sync client uses them to mint a per-participant access token for each meeting
participant it mirrors into the room.

Note that the LiveKit **server URL** is part of this credential, not part of the per-bot request —
so one Attendee project maps to one LiveKit deployment.

---

## The one API call we make

```http
POST /api/v1/bots
Authorization: Token <attendee_api_key>
Content-Type: application/json

{
  "meeting_url": "https://meet.google.com/abc-def-ghi",
  "bot_name": "<assistant_name>",
  "metadata": {"room_name": "<our livekit room name>"},
  "room_sync_settings": {
    "sync_to_room": true,
    "livekit": {
      "room_name": "<our livekit room name>",
      "source_participant": {"publish_on_behalf": "<our livekit room name>"}
    }
  }
}
```

The schema is `ROOM_SYNC_SETTINGS_SCHEMA` at `bots/serializers.py:1145`.

- `sync_to_room: true` makes the bot mirror the meeting's participants, audio and chat into our
  LiveKit room. Set it to `false` only when several agents share one room.
- `source_participant` identifies the LiveKit participant whose audio the bot streams back into the
  meeting. Omitting it means the bot listens but never speaks. Exactly one of `identity` or
  `publish_on_behalf` must be given.
- `metadata.room_name` is how the webhook handler in plan 02 finds the matching `CallRecord`.

### Why `publish_on_behalf` rather than `identity`

A LiveKit agent's own participant identity is minted by the LiveKit server inside the job token. We
do not choose it and cannot know it before the agent has joined, so `identity` would force our API
to poll the room and wait — a race, and latency on every call.

`publish_on_behalf` matches on a participant *attribute* instead. Attendee's own description:

> The bot streams tracks from the first participant whose `lk.publish_on_behalf` attribute equals
> this value, which is how a LiveKit agent publishes on behalf of another participant.

The value is ours to choose, so our agent sets `lk.publish_on_behalf` to our room name when the
session starts (plan 02, change 6), and the match becomes deterministic with no polling.

The caveat is that `lk.publish_on_behalf` is defined in the LiveKit Agents SDK as an *avatar
worker* convention — `livekit-agents/livekit/agents/types.py` documents it as "the identity of the
agent participant that an avatar worker is publishing on behalf of", and
`livekit-agents/livekit/agents/voice/room_io/_output.py` reads it. We use no avatar plugin, so
nothing should contend for the attribute, but this must be proven before anything else is built.
It is open item **V1**, and step 2 of the verification sequence below exists to settle it.

---

## Resource budget

Attendee's own bot pod spec budgets roughly **4 vCPU and 4 GiB per bot**, one bot per meeting, one
container per bot. Ten concurrent Google Meets is about 40 vCPU before our agent workers are
counted at all.

That is a different cost class from a SIP call, which needs only a bridge process and an RTP port.
It is the reason plan 02 gives Meet calls their own concurrency bucket rather than letting them
share the telephony or web caps.

## Failure modes to expect

**Waiting room.** An anonymous bot has to be admitted by a host. Attendee models this as the
`waiting_room` state, and its automatic-leave settings decide how long to wait before giving up.
Whether our Workspace tenant even permits external participants is open item **V6**.

**Meet DOM changes.** Google ships UI changes on its own schedule and any of them can break the
join flow. This is the permanent maintenance tax on the browser-bot approach, and it is the main
argument for tracking upstream rather than forking: upstream fixes these, we do not.

**Licensing.** Attendee is under the Elastic License 2.0 — source-available, but not an OSI open
source licence. ELv2 forbids providing the software "as a hosted or managed service" to third
parties. Running it for our own meetings is clearly fine. Offering Meet bots to our customers as a
product feature is the open question, and it is a legal answer rather than a technical one. The
decision taken was to build the spike now and settle this before anything ships.

**Policy.** Google's Workspace API developer policy conditions its approved use case on access
"via a user interface for the benefit of users" and prohibits using "multiple accounts to bypass
Meet account limitations". Commercial notetaker bots all operate in this same grey area. Worth a
conscious decision rather than a discovery later.

---

## Open items

These are the things that must be settled before, or during, the first steps of the build. They are
numbered so plan 02 can refer to them.

| # | Question | How to settle it |
|---|---|---|
| V1 | Does `source_participant.publish_on_behalf` match an attribute our own agent sets, given that the SDK defines `lk.publish_on_behalf` as an avatar-worker convention? | Two-participant smoke test against a LiveKit room, before any Meet is involved. Verification step 2 below |
| V2 | If V1 fails, fall back to `source_participant.identity`, which means our API must discover the agent's identity after it joins — `ListParticipants` filtered on `kind == AGENT`. `dispatcher.py:293` `_watch_agent_join` is existing machinery for "the agent has joined" | Only if V1 fails |
| V3 | Can a bot be configured to join **without** recording? The state machine has a `joined_not_recording` state, which suggests yes, but the required S3 bucket variable suggests recording is assumed | Read the recording settings in `bots/serializers.py`, then try a bot with recording off |
| V4 | Attendee's webhook payload shape and its signature verification scheme | Attendee's `docs/webhooks.md` |
| V5 | Does the `docker-compose-multi-host` launcher need the Docker socket mounted, and is that acceptable on our host? | `bots/tasks/run_bot_in_ephemeral_container_task.py` |
| V6 | Does a Meet bot need host approval on every join, and does our Workspace tenant allow external participants at all? | Try it against a real meeting |

Items that the research phase could not confirm from a primary source are listed at the end of
[`docs/research/google-meet-agents.md`](../docs/research/google-meet-agents.md).

---

## Verification

Each step is independently checkable, so a failure localises instead of leaving us guessing which
half is broken.

1. **The stack comes up.** `docker compose up`, create the single admin user, add the LiveKit
   credential, then `curl` the bots endpoint with a malformed body and confirm a 400. This proves
   routing, authentication and the database, and nothing else.
2. **Room sync works in isolation.** Create a bot pointed at a throwaway Meet with
   `room_sync_settings` only, and no agent anywhere. Watch our LiveKit room: the meeting's
   participants should appear as LiveKit participants publishing audio. This proves the LiveKit
   credential, settles **V1** and **V3**, and is the single highest-value step in the whole plan.
3. **The agent hears the meeting.** Dispatch our agent into that room by hand. It should transcribe
   a human speaking in the Meet. This proves the inbound half.
4. **The meeting hears the agent.** Add `source_participant` and confirm the agent's speech comes
   out of the Meet. This proves the outbound half, and is the moment the feature exists.

Steps 5 onward belong to plan 02.
