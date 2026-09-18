# Plan 01 — The meeting connector service

Everything in this document lives **outside** `api_livekit`. Its counterpart,
[`02-api-livekit-integration.md`](./02-api-livekit-integration.md), covers the changes inside this
repo. The two meet at exactly two contracts: the environment block the connector is launched with,
and the status callback it posts back.

## What the connector is

`agent-tracking/demo-code/standalone_google_meet/` is a working prototype that joins one Google
Meet as an anonymous participant and bridges audio in both directions with a LiveKit room. It is
roughly 1,400 lines of Python plus the browser payloads, and it already does the whole job:

- **Inbound.** The injected page script taps Google Meet's WebRTC audio receivers and streams raw
  PCM to the Python process over a local WebSocket
  (`assets/google_meet_chromedriver_payload.js`, `src/standalone_google_meet/websocket_server.py`).
  Python publishes that audio into our LiveKit room
  (`src/standalone_google_meet/livekit_sync.py`).
- **Outbound.** Python mints a short-lived, hidden, subscribe-only LiveKit token and injects it
  into the page. The browser-side adapter (`assets/livekit-client-adapter.js`) connects to LiveKit
  *through the connector's own WebSocket relay* — the `/rtc` branch of
  `websocket_server.py::_handle` proxies to the upstream `LIVEKIT_URL` — subscribes to one
  designated LiveKit participant, and feeds that audio into the virtual microphone Google Meet
  reads from. The assistant's voice never round-trips through Python, and the LiveKit API secret
  never reaches the browser.

An earlier version of this plan proposed self-hosting `attendee-labs/attendee` for exactly this
bridge. That is now obsolete. This connector is the same capability without the Django
application, the Postgres database, the Celery workers, the Elastic License, or the five features
we would have had to switch off. **We host Attendee nowhere and depend on it for nothing.**

## What still has to be built around it

The prototype is a single process configured entirely by environment variables, joining one
meeting for its whole lifetime, with no way to be started or observed from outside. Four things
close that gap.

### 1. One mixed audio track instead of one per speaker

This is the highest-priority change in either plan, because without it the feature looks like it
works and does not.

`livekit_sync.py::_add_participant` currently opens a separate `rtc.Room` connection for every
human in the meeting, each publishing its own mono track under that person's Meet `deviceId`.
LiveKit's `AgentSession` links to a single participant — per the LiveKit documentation on agent
sessions, "the linked participant is the one the agent listens and responds to. By default, links
to the first participant that joins the room." With three people in the meeting, our assistant
would hear one of them and be deaf to the other two.

The fix needs almost no new code, because Google Meet has already mixed the audio for us. The page
builds a mixed `MediaStreamDestination` at `google_meet_chromedriver_payload.js:380` and there is a
complete sender for it at `:1462`, emitting message type `3` with no participant id — it is simply
switched off. In `chrome_session.py:121-122`:

```python
"sendMixedAudio": False,
"sendPerParticipantAudio": True,
```

Flip both. Then teach `websocket_server.py::_handle` to accept `protocol.MIXED_AUDIO` (already
defined as `3` in `protocol.py`), and collapse `livekit_sync.py` to a single room connection under
a fixed identity such as `google-meet`, publishing one track.

The result is that our LiveKit room contains exactly one remote human-side participant carrying
the whole meeting, which is the same shape as a phone call. Nothing in `session.py` needs to know
that several people are talking.

What we give up is per-speaker attribution in the transcript. The connector still emits
`UsersUpdate` messages naming everyone in the meeting, so the roster is not lost — only the
mapping from a spoken sentence to a speaker. Keep the per-participant path behind the flag; when
diarization becomes a requirement, the code to restore it is still there.

**To verify:** the mixed sender passes `audioData` as `Float32Array` after down-mixing to mono
(`:465-475`), and the frame comes from a `MediaStreamTrackProcessor` on Meet's own `AudioContext`,
so the sample rate is whatever that context negotiated. Confirm it is 48 kHz before trusting
`LIVEKIT_AUDIO_SAMPLE_RATE`'s default.

### 2. Selecting our assistant as the outbound source

`config.py` already supports both ways of naming the LiveKit participant whose audio goes into the
meeting, and rejects setting both:

- `LIVEKIT_SOURCE_IDENTITY` — an exact participant identity.
- `LIVEKIT_SOURCE_PUBLISH_ON_BEHALF` — a value matched against the participant's
  `lk.publish_on_behalf` attribute.

**Use the second one.** A LiveKit agent's participant identity is minted server-side inside the job
token; we do not choose it and cannot know it before the agent has joined. Matching on identity
would force the API to poll `ListParticipants` until the agent appears, and then reconfigure a
connector that has already started. Matching on an attribute the agent sets about itself removes
the race entirely: we pass the LiveKit room name as the expected value, and the agent sets
`lk.publish_on_behalf` to its own room name on startup (plan 02, change 6).

The one thing to confirm is that the LiveKit Agents SDK does not object. `lk.publish_on_behalf` is
defined there as an avatar-worker convention (`livekit-agents/livekit/agents/types.py`, read by
`voice/room_io/_output.py`). We configure no avatar, so nothing should contend for it, but this is
unproven and is verification step 2 below.

### 3. A lifecycle callback

The connector currently reports nothing to anyone. Our API needs to know when the bot actually got
into the meeting and when it left, otherwise every Meet call sits at `call_status="initiated"`
forever — the same way web calls do today, since `"answered"` is only ever set from the Exotel
bridge's `call_answered` message.

Add two environment variables and a handful of lines of `httpx`:

```
CONNECTOR_STATUS_URL=http://<our api>/call/meet/status
CONNECTOR_STATUS_TOKEN=<shared secret>
```

POST a small JSON body — `{"room_name": ..., "status": ..., "detail": ...}` — at four moments the
connector already knows about:

| Moment | Where it is detected today | `status` |
|---|---|---|
| Waiting for admission | `chrome_session.py::_wait_until_admitted` | `waiting` |
| In the meeting | `_is_in_call` returns true | `joined` |
| Join refused or timed out | `_raise_if_blocked`, `_raise_if_denied`, `_reject_invalid_meeting` | `failed` |
| Left or shut down | the `finally` block in `cli.py::main` | `ended` |

Send the room name rather than any connector-side id, because the LiveKit room name is the only
identifier both sides already agree on. Authenticate with a static bearer token; this is an
internal network call and nothing more elaborate is warranted.

### 4. Packaging as a launchable unit

`docker-compose.yaml` today builds one long-lived container from `.env`. Per call we instead want
one container, started with that call's environment, which exits when the meeting ends.

Keep `network_mode: host` (the connector reaches LiveKit and serves its own WebSocket on
`127.0.0.1`) and keep `shm_size: 2gb` — Chrome will crash on Docker's 64 MB default. Add
`--rm` so containers do not accumulate, and keep the `./artifacts` mount: `_save_artifacts` writes
a screenshot and DOM dump on every failed join, which is the only useful evidence when Google
changes the join flow.

Whether the API shells out to `docker run` or talks to the Docker socket is plan 02's decision
(change 5). Either way the connector image must be built and available on the host that runs the
API.

Budget roughly 1 vCPU and 2 GiB per concurrent meeting, dominated by headful Chrome. Measure it
before trusting it; the cap in plan 02 is set conservatively for this reason.

## The launch contract

This is the interface between the two plans. The API sets these and nothing else:

```
MEETING_URL=https://meet.google.com/abc-def-ghi
BOT_DISPLAY_NAME=<assistant name>
LIVEKIT_URL=<same as ours>
LIVEKIT_API_KEY=<same as ours>
LIVEKIT_API_SECRET=<same as ours>
LIVEKIT_ROOM=<the room our agent was dispatched into>
LIVEKIT_SOURCE_PUBLISH_ON_BEHALF=<the same room name>
CONNECTOR_STATUS_URL=http://<our api>/call/meet/status
CONNECTOR_STATUS_TOKEN=<shared secret>
```

`LIVEKIT_SOURCE_PUBLISH_ON_BEHALF` being the room name is deliberate: it is a value both sides
already hold, unique per call, and needs no coordination.

## Keeping the platform seam clean

The next platform will be Zoom or Teams. The existing split is already the right one and needs no
refactor to stay that way — it only needs to not be violated:

| Platform-specific | Reusable |
|---|---|
| `chrome_session.py` | `livekit_sync.py` |
| `assets/google_meet_chromedriver_payload.js` | `websocket_server.py` |
| `humanized_input.py`, `x11_input.py`, `mocap_manager.py` | `protocol.py`, `config.py` |
| | `assets/livekit-client-adapter.js`, `assets/shared_chromedriver_payload.js` |

The left column is "how do I get a browser into this product's meeting and find its audio". The
right column is "how does audio move between a browser page and LiveKit", and it does not know
what Google Meet is. A second platform is a new payload script and a new session class; nothing in
the right column should change.

The rule that keeps this true: `livekit_sync.py` must never import from `chrome_session.py`, and
the WebSocket protocol in `protocol.py` must stay platform-neutral. If a Zoom-shaped field wants to
appear in `protocol.py`, that is the signal the seam is being crossed.

## Where the code should live

It is a prototype under `agent-tracking/demo-code/` today, which is fine for the spike and wrong
for anything past it — it ships a committed `.venv`, a `.env` with real LiveKit credentials, and
`__pycache__`. Before it becomes a dependency of the API:

1. Delete `.venv/`, `.ruff_cache/`, `__pycache__/` and the committed `.env`, and add them to
   `.gitignore`.
2. **Rotate the LiveKit API key and secret in that `.env`**, since they are now in git history.
3. Move it to its own repository, or at minimum to a top-level directory with its own build. It has
   its own `pyproject.toml`, Python version and Chrome dependency; it should not be entangled with
   the API's.

## Known risks

- **Google changes Meet.** The page payload reads Meet's private WebRTC and participant
  structures. This is a permanent maintenance cost of any browser-bot approach and there is no
  version of this feature without it. Pin the Chrome and ChromeDriver versions in the image.
- **Join refusal.** Anonymous bots are the case Google is most likely to block. This is why
  `ui_interaction_mode` defaults to `humanized` and drives real X11 pointer and keyboard input —
  `config.py:26-28` records that WebDriver clicks only work for a signed-in profile. Expect to
  revisit this.
- **Admission policy.** A host may have to admit the bot every time, and a Workspace tenant may
  forbid external participants outright. Test against the actual tenant early; the answer may
  force a signed-in service account instead of an anonymous join.
- **Provenance.** The browser payloads under `assets/` closely track Attendee's, which is Elastic
  License 2.0 — a license that permits internal use but forbids offering the software as a hosted
  service to third parties. Internal use is fine. Before this is part of a product sold to
  customers, someone has to establish where these files came from and under what terms.

## Verification

Each step is independently checkable, so a failure localises. Steps 5 to 7 are in plan 02.

1. **The connector still joins.** Run it unchanged against a throwaway meeting, exactly as it
   works today. This is the baseline everything else is measured against.
2. **`publish_on_behalf` selects the right participant.** No Google Meet involved. Connect two
   clients to a LiveKit room, one of them setting `lk.publish_on_behalf`, and confirm the
   connector's browser adapter subscribes to that one. Settles the only real unknown in this plan.
3. **Mixed audio reaches LiveKit as one participant.** With the flags flipped, join a meeting with
   two humans talking and confirm our room shows a single remote participant whose track carries
   both voices.
4. **The assistant is audible in the meeting.** Dispatch an agent into that room by hand. Its
   speech should come out of Google Meet. This is the moment the feature exists.
