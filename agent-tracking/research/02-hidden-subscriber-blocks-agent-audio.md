# Research — two faults kept the assistant silent in Google Meet

**Resolved 2026-09-20.** Meeting calls now carry the assistant's voice, its transcript and its
recording. Two independent faults had to be fixed, both in
`~/CODE/Hirebot/livekit-connector-service`; nothing in `api_livekit` changed.

1. The browser subscribed with `hidden: True`, so the publisher was never notified and the agents
   SDK held every audio frame back. Sections below document this.
2. With frames finally flowing, the browser's single-slot `MediaStream` kept only one of the
   assistant's two audio tracks. The adapter now mixes them. See
   [Second fault: the browser kept one track instead of mixing](#second-fault-the-browser-kept-one-track-instead-of-mixing).

Background audio stays **enabled** for meeting calls. The guard added in commit `4f8ed75` is not
needed once the browser mixes, which is why `src/core/agents/session.py:1065` reads:

```python
background_audio = build_background_audio(interaction_config)
```

Citations without a prefix are in `api_livekit`. Citations prefixed `connector:` are in
`livekit-connector-service`. Citations prefixed `sdk:` are in the installed `livekit-agents`
1.7.1 and its `livekit.rtc` under `api_livekit/.venv/lib/python3.12/site-packages/livekit/`.

This document supersedes the hidden-subscriber conclusion in
`01-meeting-call-audio-silence.md`, which was inferred rather than observed and is wrong. The
connector `ready` race that document diagnosed is genuinely fixed: the run analysed here publishes
`ready` and the agent receives it.

## Symptoms

A Google Meet call on 2026-09-20 at 15:09, room
`08837cd9-0822-4442-a066-edaef7c56408_b5ad3254`, agent job `AJ_fpBhX4ZtR2dL`, connector job
`AJ_a7qrDBkfY9ac`:

- The meeting hears the assistant's background ambience but never its voice.
- The recording contains the meeting participants and the ambience, and no assistant speech.
- No assistant transcript is produced.
- Usage is accounted normally: `llm_tokens=4589`, `tts_chars=101`, `stt_audio=100.2s`.

Disabling background audio for meeting calls changes only whether the ambience is audible. Every
other symptom is unaffected.

That result was read at the time as ruling out the track-collision hypothesis recorded in commit
`4f8ed75`. It does not. Both tracks were silent while this first fault held every frame back, so
the experiment could not tell them apart. The collision was real and surfaced the moment audio
started flowing — see the second fault below. The one thing the result does establish is that the
ambience reaches Meet by a path the assistant's voice does not, which is the clue to the cause
below.

## First fault: the hidden subscriber

The connector's browser subscribes to the assistant's audio track. The LiveKit server never tells
the assistant that anyone did, so the agents SDK holds every audio frame back.

Two log lines, from the two processes, are decisive together.

The connector's browser subscribes at 15:09:43.922 and 15:09:43.924. Both publications belong to
`agent-AJ_fpBhX4ZtR2dL`, the assistant:

```
Browser reported LiveKitTrackAdded: {'type': 'LiveKitTrackAdded', 'participantIdentity': 'agent-AJ_fpBhX4ZtR2dL', 'publicationSid': 'TR_AMkBNEoMvDLxb2', 'kind': 'audio', 'id': '86f5e054-4899-4e00-b2eb-1bda2e25a6e6'}
Browser reported LiveKitTrackAdded: {'type': 'LiveKitTrackAdded', 'participantIdentity': 'agent-AJ_fpBhX4ZtR2dL', 'publicationSid': 'TR_A6eWccTbrSpwH', 'kind': 'audio', 'id': '11b9b9b2-0c03-474b-a9ab-1a9e49113343'}
```

Thirteen seconds later the assistant still believes nothing has subscribed
(`src/core/agents/session.py:1364`):

```
Agent audio track still has no subscriber 15s after the connector reported ready — its browser never subscribed, so the meeting cannot hear the assistant and nothing it says is recorded or transcribed
```

### Why the publisher is never told

RoomIO publishes the assistant's microphone track and then waits for a subscriber before it
forwards a single frame (`sdk:agents/voice/room_io/_output.py:83-91`):

```python
self._publication = await self._room.local_participant.publish_track(track, self._publish_options)
await self._publication.wait_for_subscription()
```

`wait_for_subscription()` awaits one future (`sdk:rtc/track_publication.py:88, 94-95`):

```python
self._first_subscription: asyncio.Future[None] = asyncio.Future()

async def wait_for_subscription(self) -> None:
    await asyncio.shield(self._first_subscription)
```

That future is resolved in exactly one place in the whole SDK — the handler for the server event
`local_track_subscribed` (`sdk:rtc/room.py:834-838`):

```python
elif which == "local_track_subscribed":
    sid = event.local_track_subscribed.track_sid
    lpublication = self.local_participant.track_publications[sid]
    if not lpublication._first_subscription.done():
        lpublication._first_subscription.set_result(None)
```

The connector's browser joins on a subscribe-only token minted with `hidden: True`
(`connector:src/standalone_google_meet/livekit/audio_sync.py:56-69`). LiveKit does not report a
hidden participant's subscriptions to publishers, so `local_track_subscribed` never arrives, the
future never resolves, and `_ParticipantAudioOutput.start()` blocks for the whole call.

### Why every symptom follows

| Observation | Explanation |
|---|---|
| Meet hears no assistant | frames are held at the publisher, before the track carries anything |
| Recording has no assistant | same cause — the track is published but never carries audio, so egress records silence from it |
| No assistant transcript | the transcript is synchronized to audio playout, which never starts |
| LLM and TTS usage is normal | the turn runs to completion; Sarvam TTS finished at 15:09:47 and the output was discarded |
| Ambience is audible | `BackgroundAudioPlayer` publishes its own track and never calls `wait_for_subscription()` |

That last row is why disabling background audio proved nothing about the real fault, and why the
earlier document reached the wrong conclusion from it.

The input direction was healthy throughout. `Meeting input track subscribed | name=meet-audio-mixed`
at 15:09:17, followed by `Sent 2043 chunks` to Sarvam STT and endpointing updates, shows the
meeting's audio reaching the model normally.

## The fix for the first fault

In `connector:src/standalone_google_meet/livekit/audio_sync.py:56-69`, mint the browser's
subscribe-only token **without** `hidden: True`. The server then reports the subscription, the
future resolves, and RoomIO starts forwarding audio.

The cost is one additional participant visible in the LiveKit room. It publishes no tracks, so the
recording is unchanged and the assistant's participant matching is unaffected — `RoomIO` links the
connector's own job participant, which publishes `meet-audio-mixed`, not the browser.

### How to verify

Run one meeting call and grep the agent log for:

```
Agent audio track subscribed — assistant audio can reach the meeting
```

It should appear within about a second of the browser's `LiveKitTrackAdded` line for the
assistant's publication. If the warning at `src/core/agents/session.py:1364` appears instead, the
token change did not take effect or `hidden` is not the only thing suppressing the notification.

One thing that looked like a fault and is not: `LiveKitTrackNotAccepted` for the connector's own
job participant is the browser correctly rejecting the connector's own mixed track.

## Second fault: the browser kept one track instead of mixing

Fixing the token made the assistant audible to the SDK but still not to the meeting. A second run
at 15:32, room `08837cd9-0822-4442-a066-edaef7c56408_3e25ed96`, agent job `AJ_rGRg8PWcNXYg`,
connector job `AJ_3sLhptjFi83R`, isolates it.

The agent side is now healthy end to end: `Agent audio track subscribed — assistant audio can reach
the meeting` at 15:32:54.341, user transcripts arriving (`received user transcript`, 15:33:19 and
15:33:31), turns committing, and `llm_tokens` climbing 0 → 4581 → 9205 → 13919 rather than freezing
after the greeting.

What gives the second fault away is `BotOutputAudioLevels`, which samples the stream the browser
feeds into Meet's microphone about once a second:

```
15:33:01  219     15:33:09  0      15:33:21  38
15:33:02  2463    15:33:10  0      15:33:22  601
15:33:03  150     15:33:11  0      15:33:23  0
15:33:04  567     15:33:12  0      ...all 0 to the end of the call
15:33:05  56      15:33:13  0
15:33:06  230     15:33:14  0
15:33:07  162
15:33:08  1527
```

Line those up against when the assistant was speaking. The greeting's TTS ran 15:33:06.300 to
15:33:08.601 and the speech completed at `conversation_item_added role=assistant` 15:33:14.068, so
the assistant was talking from 15:33:08 to 15:33:14 — every sample in that window reads `0`. The
second reply ran 15:33:21.284 to 15:33:22.924 and completed at 15:33:28.627; 15:33:23 through
15:33:28 also read `0`.

The stream is silent exactly while the assistant speaks and non-silent while it does not. The
non-silent runs are the background ambience, confirmed by `background_sound=True` in this
assistant's config (`src/core/agents/session.py:397`) and by the player's own line at 15:33:31.815:

```
AudioMixer: stream <async_generator object BackgroundAudioPlayer._play_task.<locals>._gen_wrapper> timeout, ignoring
```

Both of the assistant's tracks were subscribed at 15:32:55 (`TR_AMWzrKwgRmAGMJ` and
`TR_AyySC7Dw2Yixz`, both on `agent-AJ_rGRg8PWcNXYg`), but the browser's `MediaStream` holds one
audio track per kind, so the later one replaced the earlier. It kept the ambience and dropped the
voice. The recording still contained the voice because egress records every published track
independently of what the browser routes.

### Why only the meeting connector hit this

Every other transport already mixes, which is why background audio has never caused this anywhere
else:

| Transport | How multiple agent tracks are handled |
|---|---|
| Web call | The LiveKit JS SDK attaches each remote track to its own audio element; the browser mixes at playback. |
| Twilio phone call | LiveKit's SIP service subscribes to every track and mixes into the PSTN leg server-side. |
| Exotel phone call | The bridge adds every audio track to its own mixer — `src/services/exotel/custom_sip_reach/inbound_worker.py:71-83`, `add_outbound_track` then `start_outbound_mixer`. |
| Meet connector | Was the only consumer that picked one track instead of mixing. |

The connector's browser adapter now merges the assistant's audio tracks through WebAudio before
handing the stream to the webcam output, so a later track adds to the mix instead of replacing
what is there. This also covers anything else that publishes from the agent participant — thinking
sounds, filler audio, a prerecorded greeting.

Because the connector mixes, background audio stays enabled for meeting calls and the guard from
commit `4f8ed75` is not reinstated.

## Why the bot's tile turns its camera on and shows a black screen

Reported from the meeting side: a few minutes in, the bot appears to switch on both its microphone
and its camera, and its tile goes from showing initials to solid black. This is designed behaviour
in the connector, not a fault, and it is on the same code path as the audio, so it corroborates the
diagnosis above rather than pointing at a second problem.

The adapter waits five seconds for a video track from the assistant and, finding none, synthesizes
one (`connector:src/standalone_google_meet/browser/assets/livekit-client-adapter.js:463-482`):

```js
let videoTrack = await waitForVideoTrack(mediaStream, 5_000);
if (!videoTrack) {
  videoTrack = createBlackVideoTrack();
  mediaStream.addTrack(videoTrack);
  window.ws?.sendJson({ type: 'LiveKitVideoTrackNotAvailable', trackId: videoTrack.id });
}
window.botOutputManager.setBotOutputMediaStream(mediaStream);
await window.botOutputManager.playBotOutputMediaStream("webcam");
```

`createBlackVideoTrack` (same file, `:509-526`) is a 1280×720 canvas filled with `#000000` and
repainted five times a second, so the browser keeps emitting frames from it.

The combined stream is then routed through the **webcam** destination. `BotOutputManager` offers
only `screenshare` and `webcam` (`connector:src/standalone_google_meet/browser/assets/shared_chromedriver_payload.js:881-903`),
and the webcam path constructs a `BotVideoOutputStream` with `turnOnInput: this.turnOnWebcam` and
`ensureMicOn` (`:582-590`). `turnOnWebcam` is bound to `turnOnCamera`, which clicks Meet's
"Turn on camera" button (`connector:src/standalone_google_meet/browser/assets/google_meet_chromedriver_payload.js:2411-2436, 2618`).

Google Meet renders a participant's initials only while their camera is off. Once the synthesized
track goes live, Meet renders the camera feed, which is black.

The connector log for the run analysed above shows the two steps 26 ms apart:

```
15:09:48.969  Browser reported LiveKitVideoTrackNotAvailable: {'type': 'LiveKitVideoTrackNotAvailable', 'trackId': '8ab9819e-522c-4360-8178-ac265de33449'}
15:09:48.995  Browser reported MicButtonClicked: {'type': 'MicButtonClicked', 'label': 'Turn on microphone', 'caller': 'turnOnMic'}
```

Throughout the call `BotOutputAudioLevels` reports `sourcePeak` between 341 and 3830, with
`trackReadyState: 'live'` and `trackMuted: False`. The browser's output plumbing is therefore
working end to end; what it carries today is the background ambience, the one assistant track that
is not gated by `wait_for_subscription()`. After the token fix, the assistant's voice reaches Meet
over this same path with no change to the webcam routing.

Two optional improvements to the tile, neither of them urgent:

- Draw the bot's name or a logo onto the canvas in `createBlackVideoTrack` instead of filling it
  black. The camera stays on, but the tile stops looking like a dead feed. A few lines of
  `fillText`.
- Do not turn the camera on when there is no remote video. `BotOutputManager` has no audio-only
  destination today, so this means adding one that calls `ensureMicOn()` without constructing a
  `BotVideoOutputStream`. Meet would then show the bot's initials, like any audio-only participant.
  This also stops the connector encoding and uploading five frames per second of 1280×720 black
  video for no content.

## Unrelated, observed in the same log

The connector worker failed to register twice before 15:08:55, burning sixteen retries each time:

```
failed to connect to livekit, retrying in 10s ... error: Cannot connect to host localhost:7880 ssl:default [Connect call failed ('127.0.0.1', 7880)]
RuntimeError: failed to connect to livekit after 16 attempts
```

Inside the connector container, `LIVEKIT_URL="ws://localhost:7880"` resolves to the container
itself. It should name the host or the compose service. This did not cause the audio fault — the
third start registered and took the job — but it delays every cold start by roughly four minutes.
