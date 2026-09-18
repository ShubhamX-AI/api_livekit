# Plan 02 — Changes in this repository

**Scope:** everything inside `api_livekit`. A new call type, a new route, a thin client for the
Attendee service, and the small edits to the agent worker that make a Google Meet call behave
correctly.

**Companion document:** [`01-attendee-service.md`](01-attendee-service.md) covers the service we
host outside this repository. The contract between the two documents is the `POST /api/v1/bots`
body defined there and the webhook payload defined here.

---

## The shape of the change

A Google Meet call is a web call with a different participant on the other end.

The LiveKit room, the agent dispatch and the `CallRecord` are identical to what
`src/api/routes/web_call.py` already does. The only difference is what happens after the agent is
dispatched: instead of handing a join token to a browser, we ask Attendee to put a bot into a
Google Meet and mirror it into the same room.

```
POST /call/meet
      │
      ├─► create_room()                          src/services/livekit/livekit_svc.py:57
      ├─► initialize_call_record()                                              :179
      ├─► create_agent_dispatch()  with call_type="meet"                         :70
      └─► POST <attendee>/api/v1/bots  with room_sync_settings
                  │
   agent joins the room                  Attendee bot joins the Meet
   sets lk.publish_on_behalf ◄───────►   mirrors humans in, streams the agent out
```

The agent stack itself is unchanged. `DynamicAssistant`, the TTS and STT factories, the voice
features, the usage accounting and the end-of-call webhook all run exactly as they do for a web
call. That is the whole point of choosing room sync over any other integration: the meeting becomes
a set of ordinary LiveKit participants, and the agent never learns that Google Meet exists.

---

## Changes, file by file

### 1. Widen the call-type enums

`src/core/db/db_schemas.py:252-253`

```python
call_type: Optional[Literal["outbound", "inbound", "web", "meet"]] = None
call_service: Optional[Literal["exotel", "twilio", "web", "meet"]] = None
```

Beanie performs no migrations, so existing rows are untouched. The compound index at `:269`,
`IndexModel([("call_status", 1), ("call_type", 1)])`, already serves the new value — it exists
precisely so the concurrency counts can be answered per call type without a second scan.

### 2. Give Meet calls their own capacity bucket

`src/services/outbound_dispatcher/dispatcher.py:67-89`

`bucket_for_call_type` today returns `WEB` for `"web"` and `TELEPHONY` for everything else. That
default is deliberate and fail-closed: an unrecognised call type lands in the scarcer bucket, which
is the safe direction to be wrong in.

A Meet bot holds an entire browser container — roughly 4 vCPU and 4 GiB, per plan 01. It is more
expensive than either existing bucket, so it needs its own:

- add `MEET = "meet"` and include it in `BUCKETS`
- add the branch to `bucket_for_call_type`
- add `MEET: lambda: settings.MAX_CONCURRENT_MEET_CALLS` to `BUCKET_CAPS`

`tests/test_capacity_buckets.py:23-26` asserts that `None` and `"something-new"` fall back to
`TELEPHONY`. That assertion stays true and must not be weakened; add a new case asserting
`bucket_for_call_type("meet") == MEET` beside it.

### 3. New settings

`src/core/config.py`, beside the existing caps at `:86-87`:

```python
self.MAX_CONCURRENT_MEET_CALLS = int(os.getenv("MAX_CONCURRENT_MEET_CALLS", "4"))
```

Default `4`, deliberately low, and — in the same spirit as the existing comment on
`MAX_CONCURRENT_SESSIONS` — **not measured**. Four concurrent bots is already about 16 vCPU of
browser containers. Raise it from a load test, with evidence, not from optimism. Say so in the
comment.

Also add `ATTENDEE_BASE_URL` and `ATTENDEE_API_KEY`.

### 4. The new route

`src/api/routes/meet_call.py` (new file)

Follow `src/api/routes/web_call.py` closely. It is the reference implementation for the whole
sequence — ownership check, capacity reservation, room, `CallRecord`, dispatch — including the
subtle part: the in-memory slot reservation is released the moment the `CallRecord` exists, because
counting hands over to the database at that point (`web_call.py:72-73`), and the `finally` block
releases it only if we bailed out before that (`web_call.py:100-103`).

Differences from the web route:

- Request schema `TriggerMeetCall` in `src/api/models/api_schemas/telephony/calls.py`, beside
  `TriggerWebCall` at `:47`: `assistant_id`, `meeting_url`, optional `bot_name`, optional
  `metadata`. Validate `meeting_url` against `https://meet.google.com/…` — a malformed URL should
  fail here, not silently become a bot that never joins anything.
- `try_reserve_slot(MEET)` rather than `WEB`.
- `job_metadata = {**(request.metadata or {}), "call_type": "meet"}`.
- `initialize_call_record(..., to_number=meeting_url, call_type="meet", call_service="meet")`.
- After `create_agent_dispatch`, call Attendee instead of minting a browser token.
- If the Attendee call fails, call `end_call(room_name)` before returning the error. Otherwise we
  leak a room with an idle agent job in it, burning a slot until the orphan reaper notices.

Mount it in `src/api/server.py` alongside the others — `:164` is the pattern:

```python
app.include_router(meet_call.router, prefix="/call", tags=["Meet Call"])
```

### 5. The Attendee client

`src/services/attendee/` (new package)

A thin async `httpx` client with two functions: `create_bot(meeting_url, bot_name, room_name)`
returning the bot id, and `leave_bot(bot_id)`. Nothing more — no retry framework, no model layer,
no abstraction over a single vendor we are not going to swap.

It goes in its own package rather than as a loose module because the repository convention is that
several related new files get a purpose-named package, decided before they are written.

The request body is specified in plan 01,
[The one API call we make](01-attendee-service.md#the-one-api-call-we-make).

### 6. Three small edits to the agent worker

`src/core/agents/session.py`

**Set the attribute Attendee matches on.** Near `mark_agent_ready` at `:1151`, after
`session.start()`, when the call is a Meet call:

```python
await ctx.room.local_participant.set_attributes({"lk.publish_on_behalf": room_name})
```

This is what makes `source_participant.publish_on_behalf` in the Attendee request resolve to our
agent without anyone having to guess the agent's server-assigned identity. The reasoning, and the
caveat about the attribute being an avatar-worker convention in the SDK, are in plan 01; proving it
is open item **V1** and it should be settled before this line is written.

**Fix the phone-call test.** `:738` reads:

```python
_is_phone_call = job_metadata.get("call_type") != "web"
```

It is a negative test, so a Meet call currently reads as a phone call and gets narrowband noise
reduction and the phone-tuned STT prompt. Meet audio is wideband. Make this a positive test or an
explicit set membership so that adding a future call type cannot silently inherit phone tuning
again.

**Zero the telephony provider in usage.** `:448-450` sets `call_service` to `None` for web calls
when building the `UsageRecord`, because there is no telephony provider to attribute cost to. The
same is true of a Meet call.

Nothing else in `entrypoint` changes. The worker determines the call kind from `ctx.job.metadata`
alone (`:295-296`) — it never reads the `CallRecord`, room metadata or participant metadata for
this purpose — so one metadata key really is the entire mechanism.

### 7. The Attendee webhook receiver

`src/api/routes/meet_webhook.py` (new file)

This is why webhooks are in scope at all. Without them a Meet call would sit at `"initiated"` for
its entire life, exactly as web calls do today: `update_call_status(..., "answered")` is currently
only ever reached from the Exotel SIP bridge's `call_answered` data message
(`session.py:1130-1137`).

Attendee's bot state machine (its `docs/basics.md`) is richer than ours. Map only what we need:

| Attendee state | What we do |
|---|---|
| `waiting_room` | Leave `call_status` at `"initiated"`; log it. The bot is waiting to be admitted |
| joined / recording | `update_call_status(room_name, "answered", answered_at=now)` |
| `ended` | `end_call(room_name)` — this fires our existing end-of-call webhook and finalises usage |
| `fatal_error` | `update_call_status(..., "failed", call_status_reason=…)`, then `end_call` |

The room is looked up from the `metadata.room_name` we sent when creating the bot.

`end_call` (`livekit_svc.py:524`) already dedupes against `TERMINAL_CALL_STATUSES`, so a duplicate
`ended` webhook is harmless — it patches a missing duration without re-firing the webhook. That
matters, because the agent's own participant-disconnect path (`session.py:1245`) will often reach
`end_call` first.

Verify the payload shape and the signature scheme against Attendee's `docs/webhooks.md` before
trusting anything in the body — open item **V4**.

### 8. Deployment

`docker-compose.yml` and `deploy.sh`

The Attendee stack is separate, not a service inside our compose file, because it brings its own
PostgreSQL and Redis. `deploy.sh` enumerates its roles explicitly (`control | agent | full`), so a
`meet` role is added that brings up that stack.

One thing to settle when writing the compose file: `api` and `sip_dispatcher` use
`network_mode: "host"` while `agent` sits on the default bridge, so there is no shared
user-defined network today. The Attendee stack either joins host networking or gets explicit port
mappings, and its webhook needs to reach our API either way.

### 9. Documentation

A change is not done in this repository until code, schemas, tests and documentation agree. A new
call type appears in more places than it first seems:

- `docs/api/calls/meet-call.md` — new, beside `web-call.md` and `passthrough.md`
- `docs/reference/compatibility.md`
- `docs/reference/troubleshooting.md`
- `docs/features.md` and `README.md`
- `mkdocs.yml` nav

`grep -rn passthrough docs/ README.md` finds every place a call type is enumerated.

Then: `uv run mkdocs build --strict` and `uv run python scripts/check_mermaid.py`. The strict build
cannot catch a broken Mermaid diagram — a bad one deploys clean and shows an error box in the
browser — so both must run.

---

## Not in scope

- **Calendar-driven joining.** Attendee supports it; we trigger manually for now.
- **Attendee recording and transcription.** We already own both, and a second copy in a second
  database splits the truth.
- **Zoom and Microsoft Teams.** Attendee supports them through the same `room_sync_settings`, so
  they are close to free once this works. They are not this change.
- **Video.** The agent is audio-only and the bot shows no camera.

---

## Verification

Steps 1 to 4 belong to plan 01 and prove that audio flows in both directions before any of this
repository's code exists. Assuming those pass:

5. **The full route.** `POST /call/meet` end to end. Then check that the `CallRecord` was written
   with `call_type="meet"`, that its status moves `initiated → answered → completed`, that a
   `UsageRecord` was upserted for the room, and that the end-of-call webhook fired.
6. **The caps hold.** Exceeding `MAX_CONCURRENT_MEET_CALLS` returns 503, and — the part worth
   checking explicitly — a Meet call in progress does not consume a telephony slot.
7. **The gates.**
   ```bash
   uv run python -m unittest discover -s tests
   uvx ruff check <touched paths>
   uv run mkdocs build --strict
   uv run python scripts/check_mermaid.py
   ```

New tests worth writing: the bucket case in `tests/test_capacity_buckets.py`, and a test that the
webhook handler maps each Attendee state to the right `CallRecord` transition.

No commit unless asked for one.
