# Plan 04 — Make Google Meet calls work end to end

## Context

Meeting calls were added in `5a98e57` ("Add Google Meet integration (LiveKit dispatcher based)").
They do not work. The bot joins the meeting, the operator hears only the assistant's background
ambience, the assistant never answers whatever is said to it, and roughly sixty seconds later
everything goes silent. Tokens are consumed for the whole of that silence and the end-of-call
webhook fires as if a call had happened.

The cause is confirmed rather than suspected. It is a race in the connector's own worker loop that
destroys the `ready` lifecycle event, compounded by an API-side readiness deadline that is shorter
than the connector's own budget and that deletes the LiveKit room when it expires. Evidence for
every claim below is in `agent-tracking/research/01-meeting-call-audio-silence.md`; this document
is the work list derived from it.

Intended outcome: a meeting call reaches `answered`, the assistant converses with the humans in the
Google Meet, the call ends cleanly, and a regression test stops the race from coming back.

Two repositories are involved:

- **core** — `/home/shubham_halder/CODE/lvk_agents/api_livekit`
- **connector** — `/home/shubham_halder/CODE/Hirebot/livekit-connector-service`

## Sequencing

1. Changes 1 and 2, in the connector, as one commit. This is the fix.
2. Change 3, in the core. Stops the agent killing a healthy connector.
3. Run one real meeting with the amplitude probe from change 6 attached. This is the moment the
   feature either exists or does not.
4. Change 5 — documentation correction, no code.
5. Change 6 — only if the probe reads zero.
6. Change 4 — token and recording hygiene, last, behind `is_meeting_call`.

## Change 1 — connector: stop destroying the `ready` event (blocking)

**File:** `connector:src/standalone_google_meet/livekit/worker.py`, the whole of `entrypoint`
(lines 26-103).

`GoogleMeetChromeSession.start()` (`connector:src/standalone_google_meet/chrome/session.py:77-80`)
returns as soon as the bot is in the meeting, and the last statement inside that call chain is
`_emit_status(READY_EVENT, None)` (`chrome/session.py:200`). The event reaches the loop through
`loop.call_soon_threadsafe` (`worker.py:47-51`), so it lands in the same wakeup as the completion
of `session_task`.

The select at `worker.py:61-69` checks `session_task` first. Both futures are done, so it takes
that branch, cancels a `status_queue.get()` task that has **already removed the item from the
queue**, never reads its result, and breaks. The `ready` event is destroyed. Control falls into
`worker.py:78-79`, `await status_queue.get()` on an empty queue, and blocks forever — which is why
the SDK has to cancel the job (`entrypoint did not exit in time, cancelling`).

**Delete the select entirely.** One queue, one consumer, every producer pushing onto it. Nothing is
ever cancelled, so nothing can be dropped, and the outcome no longer depends on which future wins:

- the browser status callback keeps writing `(event, detail)` tuples as it does today;
- the join thread's completion becomes a `_JOIN_FINISHED` sentinel on the same queue — a successful
  join is *not* the end of the job, because the connector stays alive until the browser reports
  `meeting_ended` through `BrowserWebSocketServer._handle_json`
  (`connector:src/standalone_google_meet/browser/websocket.py:62-73`), so the loop simply continues;
- a join that raises pushes `(FAILED_EVENT, str(error))` instead of propagating;
- **new:** a `ctx.room.on("disconnected")` handler pushes a `_SHUTDOWN` sentinel. The room going
  away is the normal end of a meeting job, because the assistant deletes it when the call finishes.
  Without this the loop waits on a queue nobody will write to again and the SDK cancels the job 15 s
  later.

Keep `ready` (`worker.py:56`) — it is what stops an `ended` being published for a job that never
became ready — and keep the `finally` block's responsibilities. `worker.py:86` references
`status_task` in the `except` handler where it can be unbound, a `NameError` that would mask the
real error; it disappears with the select.

Behaviour change to make deliberately: a failed join currently re-raises, and LiveKit marks the job
failed. Publishing `FAILED` and exiting cleanly is better, because the agent already handles that
event by marking the call failed and tearing down (`src/core/agents/session.py:1229-1245`), and a
raised exception gives it nothing. Add a `raise` after the loop if the job should still be marked
failed.

**Risk:** low — strictly fewer moving parts than what is there now. The one thing to get right is
that the job must not exit when the join thread finishes, which is what the regression test asserts.

## Change 2 — connector: deterministic cleanup

**File:** same.

`ctx.add_shutdown_callback` (`sdk:livekit/agents/job.py:565-577`) is the right hook for *cleanup*
and the wrong hook for unblocking the loop. Verified in
`sdk:livekit/agents/ipc/job_proc_lazy_main.py:378-391`: shutdown awaits `_shutdown_fut`, then gives
the entrypoint 15 s and cancels it, and runs the shutdown callbacks only afterwards. A callback
cannot wake a blocked entrypoint — the `room.on("disconnected")` sentinel in change 1 is what makes
the exit prompt. The callback is the safety net for the cancel path and for worker drain, where the
room does not disconnect first.

Extract one guarded cleanup — closing Chrome, the WebSocket server, Xvfb and `audio_sync` — and
register it both in the `finally` and through `ctx.add_shutdown_callback`, with a flag so it runs
once. `GoogleMeetChromeSession.close()` (`connector:.../chrome/session.py:306-315`) already
null-guards `driver`, `websocket_server.server` and `display`, so calling it when the join never
started is safe.

**Risk:** low. The callback must be idempotent with the `finally`, since both can run.

## Change 3 — core: deadlines that do not fight the connector

**Files:** `src/core/config.py:117-119`, `src/core/agents/session.py:1341-1346` and `:674-681`.

The connector allows a human **300 s** to admit the bot
(`connector:src/standalone_google_meet/config.py:27`). The core allows **60 s**, twice, from two
different starting points, and on expiry deletes the LiveKit room (`session.py:1347-1357` →
`:660-672`), destroying a connector that was still legitimately waiting.

These are two different questions and get two settings:

| Setting | Default | Bounds |
|---|---|---|
| `MEETING_CONNECTOR_JOIN_TIMEOUT_SECONDS` | `120` | The connector *participant appearing in the room* — container start, process init, `audio_sync.start()`. Took 3 s in the captured log. Used at `session.py:1341-1346`. |
| `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS` | `360` | The connector reporting `ready`. Must exceed the connector's own 300 s so that the connector's `failed` arrives first and carries a real reason. Used at `session.py:674-681`. |

Document the coupling where the default is defined: 360 is only correct while the connector's
`WAITING_ROOM_TIMEOUT_SECONDS` is 300.

**Optional, and probably not worth building:** having a `waiting` event restart the readiness clock.
`_handle_meeting_connector_event` (`session.py:1211-1231`) already receives `waiting`, so it is a
small change — but it is machinery for a case the fixed numbers already cover. The connector bounds
itself at 300 s and emits `FAILED` on expiry, and a connector that dies outright disconnects its
participant, which is the *primary* participant, so `on_participant_disconnected`
(`session.py:1378-1396`) already ends the call promptly. Build it only if a real deployment shows
admissions running past six minutes.

**Risk:** low. One regression to accept: a dead connector that still holds its participant ties up
a `MEETING` capacity slot for six minutes rather than one (`MAX_CONCURRENT_MEETING_CALLS`,
default 4).

## Change 4 — core: stop burning tokens before the connector is ready

**File:** `src/core/agents/session.py`. **Land this after 1 to 3 are verified working.**

A moderate reorder, roughly 40-60 lines, not a large refactor — but not free, and not the bug. The
ordering today:

- `:431-432` recording starts immediately
- `:1180` the `data_received` handler is registered
- `:1263` `session.start()` — where the realtime model connects and billing begins
- `:1276` `lk.publish_on_behalf` is set
- `:1340-1346` wait for the connector participant
- `:1528` / `:1606` wait for `ready`, then greet

For `is_meeting_call` only, insert before `:1263`: `await ctx.connect()` (required — the room is not
connected before `session.start()`, see the comment at `:1170-1179`, and it is idempotent per
`sdk:job.py:622-624`); set `lk.publish_on_behalf` here instead of at `:1276`, which also closes the
race the research document flags; wait for the participant with the join timeout; wait for `ready`;
then `session.start()`. The existing blocks at `:1340` and `:1528`/`:1606` become no-ops and can
stay.

Two real costs:

- **`_flush_and_end_call` on a session that never started.** It is only reachable after
  `session.start()` today. The new bail-out paths would call it on an unstarted `AgentSession`, so
  it needs a guard or a narrower pre-start teardown.
- **Recording.** `:431-432` starts egress for every non-Exotel call; for a meeting call it should
  move behind `ready` or the recording is minutes of silence. `RecordingManager.start_once()`
  (`session_lifecycle.py:84-92`) is already idempotent, so this is a one-line move.

**Cheaper alternative if the reorder is not wanted:** leave the ordering alone and, for meeting
calls, set `speech_gate.muted = True` until `ready` — the same lever `InputGuardController` uses at
`session.py:1517`. Realtime input-audio tokens are the bulk of the burn, and silence keeps the
stream flowing, which is exactly why `muted` exists rather than detaching the input. About five
lines. It does not remove the session-open cost, only the per-second one.

**Risk:** medium. This is the hottest function in the repository and every call type flows through
it. Gate every line on `is_meeting_call`.

## Change 5 — `publisher data channel '_data_track' closed unexpectedly`

Documentation only, no code.

A reading of the Rust SDK reports that `publish_data` uses the `_lossy` or `_reliable` data channel
depending on `DataPacketKind` and never `_data_track`, which serves the DataTrack feature, and that
the `closed unexpectedly` handler only logs. That was not independently confirmed here, but the
behaviour corroborates it: the connector received `lk.agent.session` byte streams at 17:13:41-45
over the same peer connection, and the race fully explains the failure without it.

Replace the "one new item to watch" paragraph in
`agent-tracking/research/01-meeting-call-audio-silence.md` with this finding so nobody re-opens it.
If the log noise is irritating, filter that one logger to `WARNING` in the connector's logging
configuration.

## Change 6 — connector: prove the mixed audio graph is not empty

**File:** `connector:src/standalone_google_meet/livekit/audio_sync.py`, `_capture_audio` at
`:116-128`.

`google_meet_chromedriver_payload.js:364-367` maps `this.audioTracks` into source nodes exactly
once, inside `startSilenceDetection` (`:356`), called once from `StyleManager.start()` (`:806`),
called once from `enableMediaSending()` (`:1271`). Receivers pushed by the `ontrack` listener
(`:2181-2183` → `:270-272`) after that instant are never connected to the destination, so the bot
is permanently deaf to anyone who joins after it.

Independently wrong, but **not proven to be what broke this call**: `ready` never fired, so the
assistant never entered conversation, and nothing in the log establishes whether the mix carried
voice.

**Measure before editing 2 500 lines of Meet-scraping JavaScript.** Add one throttled line
computing `np.abs(np.frombuffer(pcm_s16le, np.int16)).max()` and logging it about once a second. A
flat zero while somebody is speaking confirms the defect; a real number clears it.

If confirmed, the fix is to make the graph incremental: move the
`createMediaStreamSource(...).connect(destination)` call into `addAudioTrack`, keep a reference to
the destination, and have `startSilenceDetection` connect whatever is already buffered. Roughly 15
lines, all inside `StyleManager`.

## Tests

The loop in change 1 is currently unreachable from a test, because it is welded into `entrypoint`
and `entrypoint` needs a `JobContext`. **Extract the seam first**, or the regression test is
fiction: a `run_meeting_session(*, session, lifecycle, events, loop)` coroutine that joins, pumps
lifecycle events and cleans up, with `entrypoint` keeping configuration parsing, `ctx.connect()`,
`audio_sync` and the `room.on("disconnected")` wiring.

**Connector** — `connector:tests/test_connector.py` already uses
`unittest.IsolatedAsyncioTestCase` with `FakeRoom` / `FakeParticipant` (`:39-88`), and
`FakeParticipant.publish_data` (`:46-47`) already records payloads, so `ConnectorLifecycle` needs no
new doubles.

| Test | Asserts |
|---|---|
| `test_ready_survives_a_join_that_returns_immediately` | Fake session whose `start()` calls `on_status(READY, None)` then returns. **Fails on today's code.** `ready` is published and the coroutine returns. Wrap in `asyncio.wait_for(..., 2)` so a regression is a failure rather than a hung suite. |
| `test_loop_exits_on_room_disconnect` | The `_SHUTDOWN` sentinel ends the loop and runs cleanup once. |
| `test_meeting_ended_is_terminal` | `ended` after `ready` stops the loop and does not publish a second `ended`. |
| `test_join_failure_publishes_failed` | `start()` raising publishes `failed` with the exception text. |
| `test_cleanup_runs_exactly_once` | The `finally` and the shutdown callback together close Chrome once. |

**Core**

| File | Test | Asserts |
|---|---|---|
| `tests/test_meeting_calls.py` | `test_ready_timeout_exceeds_the_connector_waiting_room_budget` | `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS >= 360`, with a comment naming the connector constant it is coupled to. The only place this cross-repository contract can be pinned. |
| `tests/test_meeting_calls.py` | `test_join_and_ready_timeouts_are_separate_settings` | Both settings exist and the join one is smaller. |
| `tests/test_meeting_dispatch.py` | `test_waiting_then_ready_then_ended_is_recorded_in_order` | Extends `test_connector_ready_is_persisted_once` (`:61`) and `test_terminal_connector_event_cannot_be_reopened` (`:86`) to the full sequence. |

**Honest gap:** `_wait_for_meeting_connector` and the participant wait are closures inside a
~1700-line `entrypoint`. There is no correct seam for testing them without extracting them, and
that extraction is a larger change than this fix warrants. Recorded rather than covered by a
shallow test that would pass regardless. If change 4 goes ahead, its new pre-start block is the
natural moment to lift both into a module-level helper that can be tested.

## Verification

```bash
# connector
cd ~/CODE/Hirebot/livekit-connector-service && uv run python -m unittest discover -s tests -v

# core
cd ~/CODE/lvk_agents/api_livekit && uv run python -m unittest discover -s tests
uvx ruff check src/core/config.py src/core/agents/session.py
uv run mkdocs build --strict && uv run python scripts/check_mermaid.py
```

Docs to update if change 3 or 4 lands: `docs/architecture/meeting-calls.md` (its "Lifecycle and
readiness" section names `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS`), `docs/api/calls/meeting-call.md`,
`docs/reference/troubleshooting.md`.

End to end, one real meeting: `POST /meeting_call/join`, admit the bot by hand, and check that

- the connector log shows `Published connector lifecycle event: {'event': 'ready'}`;
- the core log shows the call moving `initiated → answered`;
- the assistant greets, and answers when spoken to;
- `lk room participants list --room <room>` shows the agent and the connector;
- leaving the meeting produces `ended`, a finalised `CallRecord`, a `UsageRecord` and exactly one
  end-of-call webhook;
- the room recording contains both voices.

Then delay admission deliberately past 60 s to confirm the room is no longer torn down, and past
300 s to confirm the connector's own timeout produces a failed call with a real reason.

## Minor items from the same log, not worth their own change

- `connector:agent_run.py:23` sets `num_idle_processes=0`, so `no warmed process available for job`
  cost 2.2 s of cold start. Set it to `1` if that latency matters; it costs one idle process.
- `CONNECTOR_MAX_CONCURRENT_JOBS` defaults to `1` (`connector:config.py:29`), so one container
  serves one meeting and immediately reports `load=1.0`. Working as designed; scale by replicas.
