# Research — why a Google Meet call connects but no audio moves

Investigation of the failure observed after commit `5a98e57` ("Add Google Meet integration
(LiveKit dispatcher based)"): the bot enters the meeting, the operator speaks, the assistant never
answers, the meeting carries noise instead of speech, the recording contains neither side, and the
end-of-call webhook still fires with LLM tokens consumed.

Both sides were read for this write-up. Citations without a repository prefix are in
`api_livekit`; citations prefixed `connector:` are in
`~/CODE/Hirebot/livekit-connector-service`; citations prefixed `sdk:` are in the installed
`livekit-agents` 1.7.1 under `api_livekit/.venv/lib/python3.12/site-packages/livekit/agents/`.
No code was changed while writing this.

## Root cause, confirmed 2026-09-19

The connector never publishes its `ready` event, because of a race in its own worker loop. A
connector log covering job `AJ_yNXZBccFvULo` (room `e327ea62-a8f0-491d-a9af-6e57634dfb07_4c0796c3`)
shows the bot admitted to the meeting at 17:13:12.592 and `Media sending enabled` at 17:13:12.736,
and then contains **no** `Published connector lifecycle event` line at all — that log statement is
`connector:src/standalone_google_meet/livekit/lifecycle.py:32` and it runs for every event the
connector emits. Nothing was ever published.

`GoogleMeetChromeSession.start()` (`connector:src/standalone_google_meet/chrome/session.py:77-80`)
runs `_start_display()`, `websocket_server.start()`, `_join_meeting()` and then **returns**. The
last statement inside that call chain is `_emit_status(READY_EVENT, None)`
(`connector:.../chrome/session.py:200`), which hands the event to the event loop with
`loop.call_soon_threadsafe` (`connector:src/standalone_google_meet/livekit/worker.py:46-50`). So
the READY item and the completion of `session_task` land on the loop in the same wakeup.

The worker's select loop (`connector:.../livekit/worker.py:57-84`) checks the wrong one first:

```python
done, _ = await asyncio.wait({session_task, status_task}, return_when=asyncio.FIRST_COMPLETED)
if session_task in done:
    status_task.cancel()
    await asyncio.gather(status_task, return_exceptions=True)
    session_task.result()
    break
```

When both are done, `session_task` wins the branch, and `status_task` — an
`asyncio.Queue.get()` that has *already taken the item off the queue* — is cancelled without its
result ever being read. The READY event is destroyed. Control then falls into

```python
while terminal_event is None:
    event, detail = await status_queue.get()
```

on an empty queue, and the entrypoint blocks there forever.

A minimal repro of just that loop shape fails deterministically, six runs out of six:

```
published=[] entrypoint_exited=False
```

Everything the operator sees follows from this single fault:

- The assistant waits on `ready` that never arrives, so it never greets and never converses.
- Background audio is still audible in the meeting, which proves the assistant's outbound path,
  the browser subscription and the virtual microphone all work.
- Sixty seconds after the agent begins waiting, its readiness timeout marks the call failed and
  deletes the LiveKit room (`src/core/agents/session.py:1347-1357`, `:660-672`). In the log that
  lands at 17:14:06 as `entrypoint did not exit in time, cancelling`, immediately followed by
  `X connection to :0 broken` — the blocked entrypoint being cancelled, then Chrome and Xvfb dying
  with it. That is the moment the meeting goes completely silent.

The fix is in the connector: drain the status queue before breaking out of the loop, and do not
cancel a `Queue.get()` task that has already completed. Findings 1 and 5 below are still real and
still worth fixing, but they are no longer the thing standing between this feature and a working
call.

Two things the same log rules out, which earlier sections of this document treated as open:

- A hidden, subscribe-only participant *does* satisfy the publisher's
  `wait_for_subscription()`. The assistant's background audio reached the meeting, so finding 3 is
  answered and is not a fault.
- `lk.agent.session` byte streams arrive at the connector participant between 17:13:41 and
  17:13:45, so the assistant session is live and producing stream traffic while it waits.

One log line looked alarming and is not: at 17:12:47.072, one second after the mixed track is
published, the connector logs `publisher data channel '_data_track' closed unexpectedly`. A reading
of the Rust SDK reports that `publish_data` uses the `_lossy` or `_reliable` channel depending on
`DataPacketKind` and never `_data_track`, which serves the DataTrack feature, and that the handler
for this condition only logs. That was not independently confirmed here, but the behaviour
corroborates it: `lk.agent.session` byte streams crossed the same peer connection minutes later. It
did not break `publish_data`.

## What the logs already prove

`app.log` contains six meeting attempts between 19:50 and 20:06 on 2026-09-18. Every one of them
ends in one of exactly two warnings:

- `Meeting connector did not join the LiveKit room before the deadline`
  (`src/core/agents/session.py:1350`) — four runs, at 19:56:32, 19:57:49, 20:00:12 and 20:06:08.
- `Meeting connector did not become ready before the deadline`
  (`src/core/agents/session.py:681`) — two runs, at 19:51:30 and 20:01:59.

Not one run logged a connector `ready` event, and every failure fired exactly 60 seconds after the
agent started waiting. That number is `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS`
(`src/core/config.py:117-119`).

Token consumption with no conversation is explained by ordering alone: `session.start()` runs at
`src/core/agents/session.py:1263`, which opens the realtime model, and only afterwards does the
code wait for the connector (`:1529`, `:1603`). The model is live and billing for the whole of
that wait.

## Correction to an earlier hypothesis

An earlier draft of this document argued that the agent links to the wrong participant because
`PARTICIPANT_KIND_AGENT` was added to the accepted kinds at
`src/core/agents/session.py:1080-1085`. Reading the connector settles it the other way.

`connector:src/standalone_google_meet/livekit/audio_sync.py:70-90` publishes the mixed meeting
track on `ctx.room.local_participant` — the connector's own job participant, kind `AGENT`. The only
other connection the connector makes is the browser's subscribe-only token, minted `hidden: True`
at `connector:.../audio_sync.py:56-69`, so it is invisible to the agent and cannot be mislinked to.

The room therefore holds exactly one *visible* remote participant, and including
`PARTICIPANT_KIND_AGENT` is **required**, not a bug. Plan 03's open question
(`agent-tracking/plan/03-worker-dispatch-redesign.md`, "Changes in the connector repository",
change 3) is answered: the job participant carries the audio, and the two repositories agree.

## Finding 1 — the two sides disagree about how long admission may take

This is the one the logs prove, and it alone accounts for every failed run.

| | Value | Citation |
|---|---|---|
| Connector's waiting-room budget | **300 s** | `connector:src/standalone_google_meet/config.py:27` |
| Agent's budget for the connector to join the room | **60 s** | `src/core/agents/session.py:1341-1346` |
| Agent's budget for the connector to report ready | **60 s** again | `src/core/agents/session.py:674-681` |

The connector's join sequence is strictly serial
(`connector:src/standalone_google_meet/chrome/session.py:182-201`): open the meeting URL, fill in
the bot name, click join, then `_wait_until_admitted()`, and only after that
`window.ws?.enableMediaSending()` followed by `_emit_status(READY_EVENT)`. Admission is a human
pressing a button in Google Meet. Sixty seconds is not a realistic budget for it, and the connector
itself says so by allowing five minutes.

The connector does publish `waiting` while it sits there
(`connector:.../chrome/session.py:220-223`), and the agent does persist it
(`src/core/agents/session.py:1204-1231`), but `waiting` does not extend either deadline.

The timeout path is destructive. `src/core/agents/session.py:1347-1357` marks the call failed and
calls `_flush_and_end_call()`, which deletes the LiveKit room (`:660-672`). A connector thirty
seconds from admission loses the room, and with it the job, out from under its own browser.

## Finding 2 — the mixed audio graph is built from a one-shot snapshot of tracks

This is the strongest candidate for "frames arrive at the worker but nothing happens".

The page collects Meet's audio receivers as they are negotiated, in an `RTCPeerConnection`
`track` listener:

```js
if (event.track.kind === 'audio') {
    window.styleManager.addAudioTrack(event.track);
}
```

(`connector:src/standalone_google_meet/browser/assets/google_meet_chromedriver_payload.js:2181-2183`,
pushing onto the array declared at `:260` and appended at `:270-272`.)

The mixing graph is built once, from whatever that array holds at that instant:

```js
this.audioSources = this.audioTracks.map(track => {
    const mediaStream = new MediaStream([track]);
    return this.audioContext.createMediaStreamSource(mediaStream);
});
```

(`:364-367`, inside `startSilenceDetection`, which is called once from `StyleManager.start()` at
`:806`, which is itself called once from `enableMediaSending()` at `:1271`.)

Nothing re-runs that mapping. A receiver negotiated after `enableMediaSending()` is never connected
to the destination node and its speaker is inaudible to the assistant for the rest of the call.

The ordering makes this likely rather than theoretical:
`connector:.../chrome/session.py:197-200` calls `enableMediaSending()` *immediately* after
admission. Google Meet negotiates the other participants' media to a newly admitted participant
around that same moment. If the array is empty or partial when the snapshot is taken, the mixed
`MediaStreamDestination` carries silence — and it still produces frames at the full rate, so the
worker logs a healthy stream of audio packets carrying nothing. That is exactly the reported
symptom.

The same one-shot design means the bot is permanently deaf to anyone who joins the meeting after
it does.

**Verification:** in the page console, compare `window.styleManager.audioTracks.length` against
`window.styleManager.audioSources.length` during a live call. Divergence confirms it. Cheaper
still: have the worker compute peak amplitude over a second of what it hands to
`capture_frame` (`connector:.../livekit/audio_sync.py:116-128`) and log it. A flat zero while
someone is speaking proves the mix is empty and moves the whole investigation into the page.

## Finding 3 — the assistant's audio is gated behind a subscriber that arrives late

`RoomIO._init_task` (`sdk:voice/room_io/room_io.py:338-354`) does this in order: await the linked
participant, then `await self._audio_output.start()`. `start()` calls `_publish_track()`, which
awaits `self._publication.wait_for_subscription()` before resolving `_subscribed_fut`
(`sdk:voice/room_io/_output.py:84-100`), and `capture_frame` awaits that same future on every frame
(`sdk:voice/room_io/_output.py:110-111`).

So the assistant captures no TTS frames until something subscribes to its track. The only
subscriber is the connector's browser participant, and the browser's LiveKit room is not connected
until `enableMediaSending()` — after admission. Everything the assistant tries to say before that
point sits behind an unresolved future while the LLM has already generated (and billed for) it.

Two things about that subscriber are worth confirming and could not be confirmed from source:

- it connects with `hidden: True` (`connector:.../livekit/audio_sync.py:56-69`). Whether a hidden
  participant's subscription satisfies `LocalTrackPublication.wait_for_subscription()` on the
  publisher is not documented either way. If it does not, the assistant is permanently mute in
  every meeting call regardless of everything else in this document. **Test this in isolation
  before changing anything else.**
- the agent sets `lk.publish_on_behalf` only *after* `session.start()` returns
  (`src/core/agents/session.py:1276`), and the adapter matches on that attribute
  (`connector:.../browser/assets/livekit-client-adapter.js:93-116`). The ordering happens to work
  today because the browser connects much later, but it is a race nobody is enforcing.

## Finding 4 — audio format and sample rate are **not** the problem

Ruled out by reading both ends. Recorded here so nobody re-opens it.

- The page pins the mixing `AudioContext` to the rate the worker declares:
  `new AudioContext({ sampleRate: window.initialData.audioSampleRate })`
  (`connector:.../google_meet_chromedriver_payload.js:358-362`), fed from
  `config.sample_rate` at `connector:.../chrome/session.py:136`, the same value passed to
  `rtc.AudioSource(self.sample_rate, 1)` at `connector:.../livekit/audio_sync.py:77`.
- Multi-channel frames are averaged to mono before sending
  (`connector:.../google_meet_chromedriver_payload.js:455-479`).
- The wire format is a 4-byte little-endian type header followed by raw float32
  (`connector:.../google_meet_chromedriver_payload.js:1411-1435`), the type constant is
  `AUDIO: 3` (`:1173-1179`), and the worker decodes exactly that:
  `MIXED_AUDIO = 3` (`connector:src/standalone_google_meet/browser/protocol.py:4`) with a correct
  float32-to-int16 conversion at `connector:src/standalone_google_meet/browser/websocket.py:80-84`.

The noise heard in the meeting is therefore not a PCM conversion fault. The assistant's audio
reaches Meet as a raw `MediaStreamTrack` handed straight into the substituted microphone stream
(`connector:.../livekit-client-adapter.js:118-164`), with no resampling step that could corrupt
it. The likelier explanations for the noise are that the substituted microphone is carrying a dead
or empty stream, or that what was heard was Meet's own artefact on a track with no live source.
Worth confirming once findings 1 to 3 are fixed and the assistant is actually speaking.

## Finding 5 — the mixed track is published before there is anything to put in it

`connector:src/standalone_google_meet/livekit/worker.py:34-41` calls `audio_sync.start()` before
Chrome is even launched, which publishes `meet-audio-mixed` immediately. The agent links to it,
starts its realtime model, and begins billing against a track that will carry silence until
admission completes — up to five minutes later by the connector's own budget.

This is the mechanism behind "tokens burned, no conversation". It is not wrong on its own — having
the track present early is what lets the agent link deterministically — but it means the agent must
not open its model until `ready`, rather than merely not *speaking* until `ready`.

## Finding 6 — lifecycle events are published exactly once, with no replay

`ConnectorLifecycle.publish` (`connector:src/standalone_google_meet/livekit/lifecycle.py:18-32`)
keeps a `_published` set and drops any repeat. LiveKit data packets are not replayed to late
subscribers. The recovery path the API relies on is the participant attribute
`lk.meeting_connector_status`, set alongside the `ready` packet (`lifecycle.py:29-30`) and read at
`src/core/agents/session.py:1359-1364` — but only once, at the moment `wait_for_participant`
returns. If `ready` is published after that check and its data packet is missed for any reason, no
second look ever happens.

Both sides define the contract independently and they currently agree:
`connector:src/standalone_google_meet/events.py` against `src/core/call_types.py:36-52`. Two copies
of a protocol with no shared test is a thing to watch, not a present fault.

## Finding 7 — the empty recording is a symptom, not a separate fault

Recording starts unconditionally for meeting calls at `src/core/agents/session.py:431-432`, and
room composite egress records whatever tracks exist. The user side was a live track carrying
silence (finding 2), and the assistant side never captured a frame (findings 1 and 3). An empty
recording is confirmation that no audio ever moved, not an egress problem.

## What is not the problem

Publishing one mixed track rather than one per speaker is correct and should stay. `AgentSession`
listens to exactly one linked participant (`sdk:voice/room_io/room_io.py:377-397`); one track per
speaker would leave the assistant hearing a single person in a multi-person meeting. Plan 01
reached this conclusion already and the connector implements it.

## Recommended order of work

1. **Fix the deadline mismatch first.** It is the only finding the logs prove, it is a two-line
   change, and until it is fixed nothing else can be observed end to end. Raise
   `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS` above the connector's
   `WAITING_ROOM_TIMEOUT_SECONDS`, let a `waiting` event restart the clock, and stop deleting the
   room while the connector job is still alive.
2. **Prove whether the mix is empty**, with the peak-amplitude log described in finding 2. This is
   one line in `audio_sync.py` and it decides whether the remaining work is in the page or not.
   If it is, rebuild the audio graph whenever `addAudioTrack` fires instead of snapshotting once.
3. **Test the hidden-subscriber question** from finding 3 in isolation: one agent publishing, one
   hidden subscribe-only participant, and check whether `wait_for_subscription()` resolves.
4. **Do not open the realtime model before `ready`.** Move the readiness wait ahead of
   `session.start()` for meeting calls. This removes the token consumption seen in every failed run
   above, and it is worth doing even after the timeouts are fixed.
5. **Set `lk.publish_on_behalf` before `session.start()`** and have the adapter react to
   `participantAttributesChanged`, so the ordering is enforced rather than merely observed.

## How a meeting call differs from a web call

Worth stating plainly, because the meeting route was modelled on the web-call route and it differs
in exactly the places that broke.

| | Web call | Meeting call |
|---|---|---|
| Route | `src/api/routes/web_call.py::get_token` | `src/api/routes/meeting_call.py::join_meeting` |
| Dispatches | one, `api-agent` (`web_call.py:76`) | two, `api-agent` and `meet-connector` (`meeting_call.py:89`, `:107-111`) |
| Who the human is | a browser the caller opens with the returned token (`web_call.py:79`) | nobody in the room — the humans are inside Google Meet |
| Visible remote participants | one, kind `STANDARD` | one, kind `AGENT` — the connector job (plus a hidden subscriber) |
| Accepted participant kinds | SDK default, `AGENT` excluded (`sdk:job.py:145-149`) | widened to include `AGENT`, correctly (`session.py:1080-1085`) |
| When the remote's audio becomes real | immediately on join | after Chrome boots, joins, and a human admits the bot |
| Who subscribes to the agent's track | the browser, on join | the connector's hidden browser participant, only after admission |
| Readiness signal | the participant's own arrival | a JSON `ready` event on the `meeting_connector_events` topic |
| Audio path | browser microphone to LiveKit, one hop | Meet to Chrome tap to WebSocket to Python to LiveKit, four hops |

The web call works because the single remote participant *is* a real audio publisher from the
moment it appears, so "link to the first participant of an accepted kind" and "wait for a
subscriber" both resolve instantly. A meeting call keeps both mechanisms but separates participant
arrival from audio arrival by a human-controlled interval — and the agent's timeouts were written
as if that interval did not exist.
