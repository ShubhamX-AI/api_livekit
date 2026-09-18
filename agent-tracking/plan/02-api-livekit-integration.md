# Plan 02 — Changes inside `api_livekit`

The connector that actually joins the meeting is [`01-meet-connector-service.md`](./01-meet-connector-service.md).
This document covers only what changes in this repository, and assumes the connector honours the
launch contract defined there.

## The shape of the change

A Meet call is a web call whose participant happens to be a browser inside a Google Meet. The
LiveKit room, the agent dispatch, the `CallRecord`, the usage record and the end-of-call webhook are
all identical to `POST /web_call/get_token`. The single difference is that instead of handing a
token to a browser, we launch a connector container and let it bring the meeting into the room.

```
POST /call/meet
    ├─ create_room()
    ├─ initialize_call_record(call_type="meet")
    ├─ create_agent_dispatch(job_metadata={"call_type": "meet", ...})
    └─ launch connector container with the room name
                 │
   agent joins ──┤── connector joins the Meet
   sets          │   publishes the meeting's audio into the room,
   lk.publish_   │   subscribes to the participant matching
   on_behalf     │   lk.publish_on_behalf and plays it into the Meet
```

Because the worker learns the call kind from `ctx.job.metadata` alone — it never reads the
`CallRecord` or room metadata for this — one metadata key is the entire mechanism on the agent side.

## Changes, file by file

### 1. Widen the call-type enums — `src/core/db/db_schemas.py:252-253`

```python
call_type: Optional[Literal["outbound", "inbound", "web", "meet"]] = None
call_service: Optional[Literal["exotel", "twilio", "web", "meet"]] = None
```

Beanie does not migrate, so existing rows are untouched. The
`IndexModel([("call_status", 1), ("call_type", 1)])` at `:269` already serves the new value — that
index exists precisely to make the per-type live-call count cheap, and a fourth type costs it
nothing.

### 2. A capacity bucket of its own — `src/services/outbound_dispatcher/dispatcher.py:67-89`

`bucket_for_call_type` currently returns `WEB` for `"web"` and `TELEPHONY` for everything else, a
deliberate fail-closed default. Leaving Meet to fall through would put it in the telephony bucket,
which is wrong in both directions: a Meet call holds no bridge and no RTP port, but it does hold a
headful Chrome, which is far more expensive than either existing bucket.

Add `MEET = "meet"` to `BUCKETS`, a branch in `bucket_for_call_type`, and an entry in `BUCKET_CAPS`.
`tests/test_capacity_buckets.py` asserts that an unknown call type falls to `TELEPHONY`; that
assertion stays true and correct, and a case for `"meet"` is added beside it.

Update the docstring at `:74-81` while you are there — it currently explains a two-bucket world.

### 3. Settings — `src/core/config.py`

- `MAX_CONCURRENT_MEET_CALLS`, default `4`. **Not measured**, in the same spirit as the existing
  note on `MAX_CONCURRENT_WEB_CALLS`. Four concurrent headful Chromes is already a meaningful
  slice of a host. Set it properly from a load test.
- `MEET_CONNECTOR_IMAGE` — the connector image tag.
- `MEET_CONNECTOR_STATUS_TOKEN` — the shared secret the connector authenticates its status
  callbacks with.

`LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` are already present and are passed
straight through to the connector.

### 4. The route — `src/api/routes/meet_call.py` (new)

Copy the structure of `src/api/routes/web_call.py` exactly. That file is the reference for the
ordering that matters: ownership check (404) → capacity reserve (503) → `create_room` →
`job_metadata` → `initialize_call_record` → `release_slot` → `create_agent_dispatch`. The subtle
part worth preserving is that the in-memory reservation hands over to database counting the moment
the `CallRecord` exists, and the `finally` releases the slot only if we bailed before that point.

Differences from the web-call route:

- Request schema `TriggerMeetCall`: `assistant_id`, `meeting_url`, optional `bot_name`, optional
  `metadata`. Validate `meeting_url` against `https://meet.google.com/…` — rejecting a bad URL here
  is much cheaper than discovering it when a container fails to join three minutes later.
- `try_reserve_slot(MEET)` rather than `WEB`.
- `job_metadata = {**metadata, "call_type": "meet"}`.
- `initialize_call_record(..., to_number=meeting_url, call_type="meet", call_service="meet")`.
- Instead of minting a browser token, launch the connector (change 5).
- If the launch fails, call `end_call(room_name)` before returning, so we do not leak a room
  holding an idle agent.
- Reject `text_only` and realtime mode the same way the web-call route does, for the same reasons.

Mount it in `src/api/server.py` beside the existing routers.

### 5. Launching the connector — `src/services/meet_connector/` (new package)

Per the repo convention that several new files belong in a purpose-named package, this is a package
from the start rather than a loose module.

It needs to do one thing: start a container with the environment block from plan 01, and be able to
stop it. The lazy implementation is `docker run --rm -d` through `asyncio.create_subprocess_exec`,
keeping the returned container id on the `CallRecord` so we can `docker kill` it. That needs no new
dependency and no Docker socket mounted anywhere.

If the API is itself containerised, this instead requires either the Docker socket mounted into the
API container or a small launcher process on the host. Decide this when the deployment shape is
settled; it does not change anything above the package boundary.

Do **not** build an abstraction over "meeting platforms" yet. There is one platform. The second one
will tell us what the seam should be, and plan 01 already keeps the connector side clean enough
that adding Zoom does not reach into this repo at all.

### 6. Agent changes — `src/core/agents/session.py`

Three edits, all small.

**Publish the attribute the connector matches on.** After the session starts, when the call is a
Meet call, the agent must announce itself:

```python
if job_metadata.get("call_type") == "meet":
    await ctx.room.local_participant.set_attributes({"lk.publish_on_behalf": room_name})
```

This is the whole of the identity problem's solution — see plan 01 §2 for why an attribute rather
than an identity. Set it early: the connector's browser adapter may already be connected and
waiting, and anything published before the attribute is set is audio nobody in the meeting hears.

**Fix the negative phone-call test — `:738`.**

```python
_is_phone_call = job_metadata.get("call_type") != "web"
```

This reads "anything that is not a web call is a phone call", so a Meet call would silently get
narrowband noise reduction and the phone-tuned STT prompt applied to wideband meeting audio. Make
it a positive test against the telephony types, or an explicit set membership. The same reasoning
applies to any other `!= "web"` test that appears later.

**Zero the telephony provider for Meet — `:448-450`.** Usage currently clears `telephony_provider`
for web calls only. A Meet call has no telephony provider either, so it belongs in the same branch.

Everything else in `entrypoint` is untouched. The discriminator at `:295-296` gains no new case,
because a Meet call genuinely is not a web call — it does not carry `text_only` and has no browser
client.

### 7. The status callback — `src/api/routes/meet_call.py` or a sibling

Plan 01 §3 defines the payload. Map it onto call status:

| `status` | Action |
|---|---|
| `waiting` | Leave `call_status="initiated"`. Log it — this is the state a human has to resolve by admitting the bot. |
| `joined` | `update_call_status(room_name, "answered", answered_at=now)` |
| `failed` | `update_call_status(..., "failed", call_status_reason=detail)` then `end_call(room_name)` |
| `ended` | `end_call(room_name)` — fires the existing end-of-call webhook and usage finalisation |

Authenticate with `MEET_CONNECTOR_STATUS_TOKEN`; this route is not part of the public API surface
and must not accept a normal user API key.

Without this route a Meet call sits at `"initiated"` for its entire life, because `"answered"` is
only ever set from the Exotel bridge's `call_answered` message. That is the sole reason the
callback exists.

### 8. Deployment

The connector image has to be built and present on whichever host runs the API. `deploy.sh`
enumerates roles explicitly (`control | agent | full`), so this is a build step added to the
relevant roles rather than a new service in our compose file — the connector is started per call,
not kept running.

Note the existing networking split: `api` and `sip_dispatcher` run with `network_mode: "host"` while
`agent` is on the default bridge. The connector also wants host networking, so it agrees with the
API by default.

### 9. Documentation

Per `CLAUDE.md`, the change is not done until code, schemas, tests and docs agree. A new call type
touches: a new `docs/api/calls/meet-call.md` beside `web-call.md` and `passthrough.md`,
`docs/reference/compatibility.md`, `docs/reference/troubleshooting.md`, `docs/features.md`,
`README.md`, and the `mkdocs.yml` nav. Grep for `passthrough` to find every place a call type is
enumerated.

Then `uv run mkdocs build --strict` and `uv run python scripts/check_mermaid.py`.

## Not in scope

- Zoom and Teams. The connector's seam makes them cheap later; they are not this change.
- Video. The assistant is audio-only and the bot shows no camera.
- Per-speaker attribution in transcripts. Plan 01 §1 explains what is traded away and how to get it
  back.
- Calendar-driven joining. The trigger is an explicit API call.
- Recording and transcription on the connector side. We already own both.

## Verification

Steps 1 to 4 are in plan 01 and must pass first — they prove the connector works at all. These
prove the integration.

5. **The route works end to end.** `POST /call/meet` against a real meeting. Then check: a
   `CallRecord` exists with `call_type="meet"`, its status moves `initiated → answered →
   completed`, a `UsageRecord` is upserted, and the end-of-call webhook fires.
6. **The caps hold.** Exceeding `MAX_CONCURRENT_MEET_CALLS` returns 503, and a Meet call in
   progress does not consume a telephony slot.
7. **The gates pass.** `uv run python -m unittest discover -s tests`, `uvx ruff check` on the paths
   touched, `uv run mkdocs build --strict`, `uv run python scripts/check_mermaid.py`.
