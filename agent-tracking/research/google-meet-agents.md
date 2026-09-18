# Putting a LiveKit Voice Agent Into a Google Meet Call

**Status:** research note, 2026-09-18. Nothing in this document is implemented.
**Constraint assumed throughout:** the solution must be open source and self-hostable. No
closed meeting-bot SaaS (Recall.ai, Attendee's hosted plan, MeetingBaas, LemonSlice) unless the
component in question is genuinely open source and can be run on our own hardware.

This page is deliberately not in the mkdocs `nav`. MkDocs logs unlisted pages at `INFO`, not
`WARNING`, so `uv run mkdocs build --strict` still exits `0` with this file present — verified
by building with a throwaway page in this directory before writing it.

## The short answer

There is no first-party Google API that lets software speak into a Google Meet meeting. Google's
only real-time media surface, the Meet Media API, is receive-only by design, and it is still in
Developer Preview behind an enrollment requirement that covers *every participant in the
conference*. Getting an agent's voice into Meet therefore means one of two non-first-party
routes:

1. A headless-ish browser bot that joins the meeting as a participant and injects synthesized
   audio as its microphone. This is what every commercial notetaker-with-a-voice does. Exactly
   one self-hostable project ships this for Meet today — Attendee — and it is licensed under
   Elastic License 2.0, which is source-available but not OSI open source.
2. Dialing the meeting's PSTN number from our existing outbound SIP path. This is architecturally
   almost free for us, but it is blocked in practice for an India-billed Workspace tenant, and it
   cannot get past a host-admission prompt.

Ranked recommendation is in [Recommendation](#5-recommendation). The rest of this page is the
evidence.

---

## 1. Google's first-party surfaces

### 1.1 Meet REST API — control plane only

The [Meet REST API overview](https://developers.google.com/workspace/meet/api/guides/overview)
describes the API as creating and configuring meeting spaces, pre-configuring access levels and
moderation, ending an active conference, reading conference records and participant session
metadata, and retrieving artifacts (recordings, transcripts, transcript entries, smart notes).
There is no media plane. Google's own
[surface index](https://developers.google.com/workspace/meet/overview) draws the line explicitly:
the REST API is for "Create and manage meetings within your app, and retrieve data from a
conference", while raw media belongs solely to the Media API.

Artifacts are post-hoc and are fetched from Drive, which puts a restricted Drive scope
(`drive.readonly` or `drive.meet.readonly`) and OAuth verification on the path — see
[authenticate and authorize](https://developers.google.com/workspace/meet/api/guides/authenticate-authorize).
The underlying features are edition-gated even though the API docs do not say so: recording
requires Business Standard/Plus, Enterprise Standard/Plus, Education Plus or the Essentials tiers
([support.google.com/meet/answer/9308681](https://support.google.com/meet/answer/9308681)), and
transcripts require Business Standard/Plus, Enterprise Standard/Plus or Education Plus
([support.google.com/meet/answer/12849897](https://support.google.com/meet/answer/12849897)).

The [v2 REST reference](https://developers.google.com/workspace/meet/api/reference/rest/v2)
exposes only `spaces`, `spaces.members` and `conferenceRecords` with its sub-resources. There is
no method to dial out, invite a phone number, or add a live participant of any kind. `phoneUser`
is read-only participant metadata, documented as
["a user dialing in from a phone where the user's identity is unknown"](https://developers.google.com/workspace/meet/api/reference/rest/v2/conferenceRecords.participants).

### 1.2 Meet Media API — receive-only, and still in preview

This is the decisive finding. The
[Media API overview](https://developers.google.com/workspace/meet/media-api/guides/overview)
lists the entire capability set as three bullets: consume video streams, consume audio streams,
consume participant metadata. There is no send path.

The [concepts page](https://developers.google.com/workspace/meet/media-api/guides/concepts) spells
it out at the SDP level: "To receive audio, the offer must include exactly 3 **receive-only** audio
media descriptions", "To receive video, the offer must include 1–3 **receive-only** video media
descriptions", and each media flow "Consists of a single, **unidirectional** flow of RTP packets".
The C++
[client configuration struct](https://developers.google.com/workspace/meet/media-api/reference/cpp/struct/meet/media-api-client-configuration)
has two fields, both inbound: `enable_audio_streams` ("three 'receive-only' audio SRTP streams will
be created, always") and `receiving_video_stream_count`. No publish field exists. Every OAuth scope
for the API ends in `.readonly`
([get started](https://developers.google.com/workspace/meet/media-api/guides/get-started)) — the
posture is baked into the auth surface, not just the docs.

Status and gating:

- Developer Preview, announced 2025-02-24 in the
  [Meet release notes](https://developers.google.com/workspace/meet/release-notes). No GA entry
  exists as of 2026-09-18.
- The overview requires that "the Google Cloud project, OAuth principal, **and all participants in
  the conference** must be enrolled in the Developer Preview Program." That last clause alone makes
  it unusable against meetings with external attendees.
- The [Developer Preview Program](https://developers.google.com/workspace/preview) requires a
  Workspace account; personal Gmail accounts are not eligible and service accounts cannot be
  registered.
- Consent is enforced technically: "Meet Media API apps are only permitted into a meeting if
  there's someone in the call that's allowed to provide consent", and "In order to provide consent
  in Google Workspace meetings, you must be in the organization that owns the meeting." Participants
  see an initiation dialog and "anyone can stop the Meet Media API during the call."
- Protocol is WebRTC — client is always the SDP offerer, DTLS handshake, SRTP media, plus two
  required data channels (`session-control`, `media-stats`), AV1/VP9/VP8, minimum 4 Mbps
  recommended bandwidth.
- Reference clients are C++ and TypeScript only
  ([cpp](https://developers.google.com/workspace/meet/media-api/guides/cpp),
  [ts](https://developers.google.com/workspace/meet/media-api/guides/ts),
  [googleworkspace/meet-media-api-samples](https://github.com/googleworkspace/meet-media-api-samples),
  Apache-2.0). **No Python client.**
- Audio is always exactly three streams; Meet routes the loudest speakers across them, and when
  participants exceed the stream cap "Meet servers transmit the audio and video streams of
  participants deemed 'most relevant'"
  ([virtual streams](https://developers.google.com/workspace/meet/media-api/guides/virtual-streams)).
- Default rate limit 6000 requests/minute (get-started page). Supported editions are listed in
  [control Media API access](https://knowledge.workspace.google.com/admin/meet/control-media-api-access-in-google-meet).
- The get-started page also states "We don't support third-party hardware clients that run Meet" and
  that the API "is restricted from collecting media from accounts that are registered to minors."

So the Media API could replace the *listening* half of a bridge — inside one Workspace, with every
participant preview-enrolled — and can never provide the speaking half.

### 1.3 Meet Add-ons SDK — no audio, and not server-side

The [Add-ons SDK overview](https://developers.google.com/workspace/meet/add-ons/guides/overview)
describes an installable web app embedded in the Meet UI, in a side panel or main stage, with
Co-Doing, Co-Watching and content sharing. It is browser JavaScript running in an iframe inside a
human's Meet client, so it requires a live human session and cannot be a server-side bot. It grants
no audio access and no audio injection. Note that this is an *absence of any grant* rather than an
explicit denial — we could not find a primary sentence saying "add-ons cannot access audio", but
Google's surface index assigns raw media exclusively to the Media API.

### 1.4 Other surfaces, all dead ends

The Live Sharing SDK has been folded into the Add-ons SDK; Co-Watching and Co-Doing were
"only available in limited preview through an Early Access Program which is now closed to new
signups" ([live sharing overview](https://developers.google.com/meet/live-sharing/guides/overview)).
It synchronizes data, not media. Hardware/interop is explicitly excluded by the Media API
get-started page. A Chrome extension is not a supported Meet API — Google's guidance treats
third-party recording tools as something admins should *block*, including by blocking their domains
and restricting extensions
([external apps are recording Meet meetings](https://knowledge.workspace.google.com/admin/support/troubleshooting/external-apps-are-recording-meet-meetings)).

### 1.5 Policy exposure

The
[Workspace API User Data and Developer Policy](https://developers.google.com/workspace/workspace-api-user-data-developer-policy)
lists approved Meet-scope use cases, of which the closest is "Built-in web and web apps that allow
for real-time processing, streaming, or storing, of audio and video from participants in the
meeting **via a user interface for the benefit of users**." An unattended server-side bot with no
user interface is not squarely inside that. The prohibited list includes "Applications that monitor
or distribute Meet user data, content, or metadata without legal authorization or without consent"
and "Applications that use multiple accounts to abuse Google policies, bypass Meet account
limitations, circumvent filters and spam, or otherwise subvert abuse or safety restrictions" — which
is uncomfortably close in shape to a dedicated bot account driving a headless browser. The policy
also bars using Workspace user data to train non-personalized ML models.

**Could not verify:** any explicit Google statement permitting or forbidding "automated" or
"unattended" clients as a named category. The
[Workspace acceptable use policy](https://workspace.google.com/terms/use_policy/) contains no
Meet-bot-specific clause. Treat the browser-bot route as policy-grey, not policy-clear, and get a
human decision before shipping it to customers.

---

## 2. The headless-browser bot route

### 2.1 What actually exists, and under what licence

| Project | Licence (verified from LICENSE) | Self-host | Platforms | Audio direction |
|---|---|---|---|---|
| [attendee-labs/attendee](https://github.com/attendee-labs/attendee) (`noah-duncan/attendee` redirects here) | **Elastic License 2.0**, © Attendee Labs LLC. GitHub reports `NOASSERTION`. Not OSI. | Yes, documented | Meet, Zoom, Teams | **Bidirectional** |
| [Vexa-ai/vexa](https://github.com/Vexa-ai/vexa) | **Apache-2.0** | Yes, fully (Docker, `process`, k8s, Helm) | Meet, Teams, Zoom, Jitsi (unvalidated) | Receive-only in open core |
| [Meeting-Baas/meet-teams-bot](https://github.com/Meeting-Baas/meet-teams-bot) | **ELv2**, © Spoke SAS | Yes | Meet, Teams | Receive-only (record/transcribe) |
| [Meeting-Baas/speaking-meeting-bot](https://github.com/Meeting-Baas/speaking-meeting-bot) | **MIT** | Yes, but | — | Can speak, **cannot join** — requires `meeting_baas_api_key` against their SaaS |
| [Meeting-Baas/meeting-bot-as-a-service](https://github.com/Meeting-Baas/meeting-bot-as-a-service) | **No LICENSE file** → all rights reserved | — | — | legacy, last push 2025-05 |
| [meetingbot/meetingbot](https://github.com/meetingbot/meetingbot) | **LGPL-3.0** | Yes (Terraform → AWS) | Meet, Teams, Zoom | Receive-only |
| [screenappai/meeting-bot](https://github.com/screenappai/meeting-bot) | **MIT** | Yes (Docker Compose) | Meet, Teams, Zoom | Receive-only; advertises "Stealth Mode" anti-detection |
| [recallai/google-meet-meeting-bot](https://github.com/recallai/google-meet-meeting-bot) | **No LICENSE file** → not OSS | PoC | Meet | Caption scraping only |

The MeetingBaas split deserves a note because it looks like a viable combination and is not: the
MIT "speaking" repo can speak but cannot join, and the ELv2 repo can join but has no speak API. You
cannot assemble join-plus-speak from MeetingBaas's open source without their hosted service.

Two negative results worth recording. **Pipecat has no Google Meet transport** — listing
[`pipecat/src/pipecat/transports`](https://github.com/pipecat-ai/pipecat/tree/main/src/pipecat/transports)
gives `daily, heygen, lemonslice, livekit, local, moq, smallwebrtc, tavus, vonage, websocket,
whatsapp`. And **Vexa's `/speak` endpoint is stubbed but not wired**: its own README states that
`POST /bots/{…}/speak` (TTS into the call) and WebSocket streaming "are not yet wired in the
open-core stack and return `404` today." Several forks and SEO pages claim Vexa bots can speak;
the repo contradicts them, and the repo wins.

### 2.2 Attendee's speaking interface

[`docs/realtime_audio.md`](https://docs.attendee.dev/guides/realtimeaudio) opens with: "Attendee
supports bidirectional realtime audio streaming through websockets. You can receive mixed or
per-participant audio from meetings and have your bot output audio into meetings in real-time."
The frame our side would send is:

```json
{"trigger":"realtime_audio.bot_output","data":{"chunk":"<base64 PCM16 mono>","sample_rate":16000}}
```

with `sample_rate` one of 8000, 16000 or 24000. The docs name OpenAI Realtime (24 kHz) and Deepgram
Voice Agent (16 kHz) as the intended sinks. There are two other speak paths we would not use: a
`POST /bots/{id}/speech` TTS endpoint whose schema accepts only Google Cloud TTS, and a
`voice_agent_settings.url` mode where Attendee loads *our* web page in a managed container and uses
its audio as the bot's microphone.

### 2.3 How injection actually works

This is the part most write-ups get wrong, and it matters if we ever build our own. Attendee does
**not** pipe TTS through a PulseAudio virtual microphone. Its in-page payload monkey-patches
`navigator.mediaDevices.getUserMedia` and hands back a WebAudio track:
`new AudioContext()` → `createGain()` → `createMediaStreamDestination()` →
`stream.getAudioTracks()[0]`. Video is `canvas.captureStream(30)`, with the in-source comment that
30 fps is required "or Google Meet complains."

The Chrome fake-device flags only suppress the permission prompt and satisfy device enumeration.
From Chromium's own
[`content_switches.cc`](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/content/public/common/content_switches.cc),
`--use-fake-ui-for-media-stream` "Bypass[es] the media stream infobar by selecting the default
device for media streams", and upstream now says to "Prefer
`--auto-accept-camera-and-microphone-capture` which does not interact with screen/tab capture."
[`media_switches.cc`](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/media/base/media_switches.cc)
documents `--use-fake-device-for-media-stream` and `--use-file-for-fake-audio-capture` ("Play a .wav
file as the microphone"), the latter being loop-or-once playback of a static file — fine for tests,
useless for a live conversation.

A PulseAudio null-sink loopback is the fallback when JS injection is not available, and is still how
audio gets *captured*. The module sources are the primary reference, since the freedesktop wiki sits
behind an anti-bot challenge:
[`module-null-sink.c`](https://gitlab.freedesktop.org/pulseaudio/pulseaudio/-/tree/master/src/modules)
("Clocked NULL sink", `sink_name=`, `rate=`, `channels=`…), `module-virtual-source.c`
("Virtual source", `master=<name of source to filter>`), `module-remap-source.c` and
`module-loopback.c` ("Loopback from source to sink").

Attendee's container shape, from its own `Dockerfile` and `entrypoint.sh`: `xvfb`, `pulseaudio` +
`pulseaudio-utils`, `libasound2`/`alsa-utils`, `ffmpeg`, gstreamer, an `~/.asoundrc` pointing ALSA's
`default` at Pulse, and a **pinned real Chrome 134.0.6998.88 with a sha256 check** plus matching
chromedriver. The real-Chrome pin is not optional — bundled Chromium lacks the proprietary codecs
Meet needs, which is also why Playwright users need
[`channel: 'chrome'`](https://playwright.dev/docs/api/class-browsertype).

**Headless is not what ships.** Attendee's `--headless=new` argument is present but commented out,
and the adapter starts `pyvirtualdisplay`'s `Display(visible=0, size=(1930,1090), use_xauth=True)`
when `DISPLAY` is unset; there is a dedicated `x11_input.py` because the bot synthesizes real X11
clicks to drive the join flow. Chrome's
[new headless documentation](https://developer.chrome.com/docs/chromium/new-headless) explains that
since 132.0.6793.0 headless shares code with regular Chrome rather than being a separate
implementation, so the old "headless can't do WebRTC" folklore is at least outdated. **Could not
verify** any primary statement that headless Chrome cannot capture or produce WebRTC audio — what we
can assert is that both production projects run headful under Xvfb and Attendee deliberately
disabled `--headless=new`.

### 2.4 What Google does to these bots

Attendee's Meet adapter contains an explicit blocking detector matching the strings "You can't join
this video call" and "There is a problem connecting to this video call", counting
`number_of_times_blocked_by_google`, with an in-source comment that "Google is blocking us for
whatever reason and we have the ability to login but we aren't using it… **Logging in will get us
unblocked.**" Its exception vocabulary is the honest feature list of this whole approach:
`UiLoginRequiredException`, `UiLoginAttemptFailedException`, `UiRequestToJoinDeniedException`,
`UiCouldNotJoinMeetingWaitingRoomTimeoutException`, `UiCouldNotJoinMeetingWaitingForHostException`,
`UiMeetingNotFoundException`. Denial detection has to handle Google's inconsistent wording
("Someone {in|on} the call {denied|has denied} your request to join"). There is a
`POST /bots/{id}/admit_from_waiting_room` endpoint precisely because admission cannot be automated
from the bot's side. Attendee also sets `--disable-blink-features=AutomationControlled`, and
screenappai advertises "anti-detection measures" — both are signs that detection is an active
arms race, not a solved problem.

Running a *signed-in* bot, which Attendee's `docs/signed_in_bots.md` says is necessary because
"Some meetings are configured to not allow anonymous users to join at all", requires a paid Google
Workspace plan on a domain we own, a dedicated non-admin user, and configuring the Attendee server
itself as a SAML SSO identity provider (self-signed cert, Legacy SSO profile). That is real
operational work and a per-bot Workspace seat.

### 2.5 Resource cost

From Attendee's Kubernetes pod creator, one pod per bot: `BOT_CPU_REQUEST` defaults to **4 vCPU**,
memory request and limit to **4Gi**, ephemeral storage to 10Gi. The voice-agent webpage streamer is
a *second* container at +1 vCPU and +4Gi with a 1Gi `/dev/shm`. So budget roughly **5 vCPU and 8 GiB
per concurrent speaking meeting**. Attendee's README also warns that its Celery mode (the dev
default) is unfit for production because bots die on container restart and "Multiple bots running in
the same Celery worker container share audio devices, so audio from separate meetings can bleed
together." That is a direct warning against the tempting shortcut of running several browser bots in
one container.

For comparison, our telephony concurrency defaults in `src/core/config.py` are
`MAX_CONCURRENT_JOBS=12` and `MAX_CONCURRENT_SESSIONS=48`. Twelve concurrent Meet bots would be
~60 vCPU / ~96 GiB of browser containers on top of the agent workers — an entirely different cost
class from a SIP call.

---

## 3. Bridging the audio into a LiveKit room

This half is the easy half, and it is well-documented. Everything below is from LiveKit's own docs
and SDK source.

A plain Python process can be a full room participant. Per
[Processing raw media tracks](https://docs.livekit.io/transport/media/raw-tracks/), publishing is:

```python
source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
track = rtc.LocalAudioTrack.create_audio_track("mic", source)
options = rtc.TrackPublishOptions()
options.source = rtc.TrackSource.SOURCE_MICROPHONE
publication = await room.local_participant.publish_track(track, options)
```

and consuming the agent's output is the mirror image:

```python
stream = rtc.AudioStream(track, sample_rate=SAMPLE_RATE, num_channels=NUM_CHANNELS)
async for frame_event in stream:
    frame = frame_event.frame
```

The same page notes that "An internal buffer holds 50 ms of queued" audio and that WebRTC commonly
uses 20 ms chunks, which sets the frame cadence for a bridge. `AudioSource.capture_frame()` is the
push API — see
[`livekit-rtc/livekit/rtc/audio_source.py`](https://github.com/livekit/python-sdks/blob/main/livekit-rtc/livekit/rtc/audio_source.py)
and the [`publish_wave.py` example](https://github.com/livekit/python-sdks/blob/main/examples/publish_wave.py).

If we would rather have the bridge read the container's virtual audio devices directly instead of
shuttling base64 PCM over a websocket, the Python SDK has a
[`MediaDevices`](https://github.com/livekit/python-sdks/blob/main/livekit-rtc/livekit/rtc/media_devices.py)
helper built on `sounddevice`/PortAudio, documented for embedded Linux at
[Hardware & devices](https://docs.livekit.io/frontends/build/hardware/) — including AEC, "to ensure
audio played through speakers doesn't get picked up again by the microphone", which is exactly the
hazard of a Pulse null-sink loopback.

Headless containers are the normal deployment: LiveKit's
[Builds and Dockerfiles](https://docs.livekit.io/deploy/agents/builds/) guidance is a glibc-based
`-slim` Debian/Ubuntu image with the system CA bundle and no display server anywhere in the
requirements. Our `Dockerfile.agent` already satisfies this.

**LiveKit has no Google Meet integration of its own.** Its participant kinds are
`STANDARD`, `AGENT`, `SIP`, `CONNECTOR`, `EGRESS`
([participant management](https://docs.livekit.io/intro/basics/rooms-participants-tracks/participants/)),
and the connector list is WhatsApp and Twilio only
([Telephony introduction](https://docs.livekit.io/telephony/)). The one documented Meet path in the
LiveKit docs is the
[LemonSlice avatar plugin](https://docs.livekit.io/agents/models/avatar/plugins/lemonslice/), whose
`join_meeting()` sends an avatar into "a Zoom, Google Meet, Microsoft Teams, or Webex meeting" via
"a LemonSlice-managed relay". That is a closed hosted relay requiring `LEMONSLICE_API_KEY`, so it is
out of scope for this brief; it is listed here only so nobody rediscovers it and thinks the problem
is solved. It does confirm the target architecture: mixed meeting audio into the agent's STT, agent
audio published into the meeting.

### How it wires into this repo

The fit is genuinely good, because a Meet bot looks like one more call type in front of an unchanged
agent session:

- `create_room()` and `create_agent_dispatch()` in `src/services/livekit/livekit_svc.py` already
  create a room and dispatch the `api-agent` worker with metadata. A Meet call would reuse both
  verbatim.
- The worker entrypoint in `src/core/agents/session.py` does not care how audio arrived; the bridge
  participant is just another remote track. Cascade mode's STT→LLM→TTS stages stay untouched.
- The bridge process is a new component — a browser-bot container plus a small Python LiveKit client
  — which by our convention means a purpose-named package (something like
  `src/services/meet_bridge/`) decided before the first file, not a scatter of new modules.
- `CallRecord.call_type` and `bucket_for_call_type` would need a new bucket. A Meet bot must **not**
  land in the telephony bucket: it holds no RTP port but does hold ~5 vCPU of browser, so it needs
  its own cap, far below `MAX_CONCURRENT_JOBS`.
- A token with the right `VideoGrants` is already generated at `livekit_svc.py:677` for web calls;
  the bridge needs the same treatment.

---

## 4. Does our existing SIP path help?

Partly in theory, not in practice for us. Detail below.

### 4.1 PSTN dial-in exists, but India does not have it

Dial-in is a paid-Workspace feature: "You can only dial-in if the meeting is organized by a Google
Workspace user", and "A dial-in number is only added when admins turn on the dial-in feature"
([support.google.com/meet/answer/9303069](https://support.google.com/meet/answer/9303069)). The
[premium features matrix](https://support.google.com/meet/answer/10459644) shows dial-in and
dial-out present from Business Starter upward, so it is not Enterprise-only.

Country coverage is the blocker.
[Supported countries](https://support.google.com/meet/answer/9683440) says "With any Google
Workspace edition, a user can connect Google Meet to phone numbers in the US. Supported Google
Workspace editions also enable dial-in to numbers from these countries and territories" and lists
roughly 68 entries. **India is not in that list.** India appears only under Meet Global Dialing
(dial-in) and, for dial-out, annotated "India (no India to India calls)". And Global Dialing itself
is gated: "This option is only available if your Google Workspace billing location is in a supported
country", listing the US, Canada, UK, France, Spain, Portugal, Denmark, Sweden, Switzerland,
Ireland, Netherlands, Germany, Italy, Austria and Belgium
([set up Global Dialing](https://knowledge.workspace.google.com/admin/meet/set-up-google-meet-global-dialing),
[support.google.com/a/answer/10162808](https://support.google.com/a/answer/10162808)). **India is not
an eligible billing location**, so an India-billed tenant cannot buy Global Dialing and cannot get an
Indian Meet dial-in number.

The practical consequence for our stack: the agent would have to place an *international* outbound
call from the Indian Exotel trunk to, say, a US Meet number. Whether Exotel or Twilio will carry
that, at what per-minute cost and with what latency and codec, is outside Google's documentation and
**was not verified** here.

### 4.2 The dial-in IVR an automated caller must survive

Per [support.google.com/meet/answer/9303069](https://support.google.com/meet/answer/9303069) and
[answer/9518557](https://support.google.com/meet/answer/9518557): "Once connected, enter the pin
followed by the # key", then "When prompted, press 1 on your phone." So two DTMF stages. `*6`
toggles mute in-call. Dial-in works "from 15 minutes before the meeting starts until it ends", and
"If you try to call into a meeting before it starts, you might get an error that the PIN isn't
recognized." Crucially, admission is not guaranteed: "if you're in a different domain than the
meeting owner, someone in the meeting might need to approve you." There is no programmatic
self-admission. Phone participants get "audio-only access", count toward the participant limit, and
incur normal call charges.

**Could not verify:** the PIN's digit count (no Google page states a length), the exact timing and
repeat behaviour of the "press 1" prompt, whether a phone-only participant can hold a meeting open
before any host joins, and whether there is a separate cap on phone participants.

### 4.3 Our DTMF situation is asymmetric

This is a repo-specific catch. LiveKit supports DTMF both as a `dtmf` field on
`CreateSIPParticipantRequest` ("Character `w` can be used to delay DTMF by 0.5 sec" —
[outbound calls](https://docs.livekit.io/telephony/making-calls/outbound-calls/)) and as an
in-room `publish_dtmf(code=, digit=)` call ([Handling DTMF](https://docs.livekit.io/telephony/features/dtmf/)).
Our Twilio path goes through LiveKit SIP via `create_sip_participant()` in
`src/services/livekit/livekit_svc.py:108`, which does **not** currently pass `dtmf` — adding it is a
one-field change.

Our Exotel path does not go through LiveKit SIP at all; it uses the custom bridge in
`src/services/exotel/custom_sip_reach/`. That bridge explicitly discards DTMF:
`_decode_rtp_payload` in `rtp_bridge.py` returns empty bytes for any payload type that is not PCMA
or PCMU, with the comment that "PT=101 (RFC 2833 DTMF), comfort noise, and any other dynamic PTs
would otherwise be alaw-decoded into garbage PCM". There is no DTMF *send* path in that bridge
either. So dialing a Meet PIN over Exotel would require implementing RFC 4733 telephone-event
generation in our own RTP bridge — not a one-liner.

### 4.4 SIP URI: no, not without Pexip

Google requires a partner gateway: "To use Meet with third-party systems, you need to use the Google
Workspace partner product Pexip Connect for Google Meet", and those systems "must be standards-based
(SIP/H.323)"
([allow 3rd-party devices](https://knowledge.workspace.google.com/admin/meet-hardware/allow-3rd-party-devices-to-join-meet-video-meetings)).
Turning interop on is included with all paid Workspace licences, but "For Pexip-based systems, you
must still purchase a license from Pexip or a Pexip partner"
([interoperability FAQ](https://knowledge.workspace.google.com/admin/meet-hardware/meet-interoperability-faq)).

Pexip's own docs require a full Pexip Infinity deployment plus a `ghm` licence, interop access
tokens and a JWT gateway token generated in Workspace
([gmeet_intro](https://docs.pexip.com/admin/gmeet_intro.htm),
[gmeet_configuration](https://docs.pexip.com/admin/gmeet_configuration.htm),
[gmeet_gsuite](https://docs.pexip.com/admin/gmeet_gsuite.htm)). The dial string is Pexip's, not
Google's — a gateway rule matching "just `<meeting ID>` or `<meeting ID>@<domain>`", or a virtual
reception IVR alias then DTMF. Direction is one-way: "Google Meet is inherently a dial-in service
i.e. you can only dial from a third-party video system into Google Meet." Documented limits include
a maximum of 8 video streams from Meet, outbound bandwidth fixed at 2 Mbps, two Pexip call licences
per gatewayed participant, and — for SIP Guest Join — a Trusted Devices licence and someone
admitting you from the lobby within about 30 seconds.

Nothing in Google's documentation offers a SIP URI, registrar or trunk into a Meet meeting. Note that
[SIP Link](https://support.google.com/a/answer/11606486) is Google *Voice* PSTN trunking, not Meet
joining. So a bare SIP UA — including a LiveKit SIP trunk — cannot dial a Meet meeting. Only the
PSTN number is open to it.

### 4.5 Meet dialing out to us is not programmable

Meet can call a phone number from inside a meeting (US and Canada on any edition, elsewhere with
Global Dialing, billed per minute —
[answer/9303164](https://support.google.com/meet/answer/9303164)), but it is a manual UI action:
People → Add people → Call. The REST API has no method for it, as established in §1.1. So "have Meet
dial our agent's number" is not automatable either.

---

## 5. Recommendation

Ranked for this repo, with the failure mode that would actually kill each one.

### Rank 1 — Attendee (self-hosted) as an audio transport, LiveKit room unchanged

Run Attendee on our own Kubernetes, use its bidirectional websocket audio, and put a small bridge
process between it and a LiveKit room: meeting audio in as a published `LocalAudioTrack`, the
agent's `AudioStream` back out as `realtime_audio.bot_output` frames. The agent session, cascade
pipeline, tools, recording and usage accounting are untouched.

Effort: roughly 1–2 weeks for a working single-meeting prototype (bridge process, a `/call/meet`
route, a new `call_type` and concurrency bucket), plus a comparable amount of unglamorous work for
the signed-in-bot Workspace and SAML setup and for Kubernetes bot-pod deployment.

Failure modes, in the order they will hurt: **licensing** — ELv2 forbids providing "the software to
third parties as a hosted or managed service, where the service provides users with access to any
substantial set of the features or functionality of the software", which is a direct problem if we
resell Meet bots as a platform feature and needs a legal answer before engineering starts; **Google
blocking**, which Attendee's own code says is mitigated by logging in, meaning a paid Workspace seat
per bot identity and an ongoing arms race; **admission**, since a waiting room or a denied join is
a human decision we cannot automate; **cost**, at ~5 vCPU and 8 GiB per concurrent meeting; and
**policy**, per §1.5. The ELv2 licence-key clause ("You may not move, change, disable, or circumvent
the license key functionality") is dormant — no enforcement code exists in the repo today — but it
is reserved.

### Rank 2 — Build our own browser bridge, copying Attendee's shape

Pinned real Chrome plus matching chromedriver, Xvfb with headful Chrome,
`--use-fake-device-for-media-stream` with `--auto-accept-camera-and-microphone-capture`, PulseAudio
for capture, and speech injected by monkey-patching `getUserMedia` to return a WebAudio
`MediaStreamDestination` track. Publish and subscribe with `rtc.AudioSource` / `rtc.AudioStream`, or
read the virtual devices directly with `MediaDevices` and get AEC for free.

Effort: substantially more than rank 1 — 4–8 weeks to reach parity — and it never ends, because the
maintenance burden is Meet's join flow changing, not the audio. Choose this only if the ELv2 answer
comes back "no". The advantage is no third-party licence at all and full control; the disadvantage
is that we would be reimplementing the hardest, least interesting part of somebody else's product.

### Rank 3 — Fork Vexa and add speaking

Apache-2.0, fully self-hostable, Meet join already works, and `POST /bots/{…}/speak` is already
stubbed and returning 404. If a genuine OSI licence is a hard requirement, this is the only path
that gets there. Effort is rank 2's audio work on top of rank 1's join work — call it 3–6 weeks —
and we inherit the same Google-blocking and admission problems plus the upstream-divergence tax.

### Rank 4 — PSTN dial-in over our existing SIP trunk

Architecturally the cheapest thing imaginable for us: a Meet dial-in number is just a phone number,
and we already dial phone numbers. It fails on facts, not on engineering. India has no Meet dial-in
number and cannot get one on an India-billed tenant (§4.1), so this needs an international call to a
foreign Meet number. It needs two DTMF stages that our Exotel bridge cannot currently produce
(§4.3). It still cannot get itself admitted from a waiting room. And it is audio-only with no roster
identity, no chat and no screen context. Worth a half-day spike if and only if the Workspace tenant
in question is billed outside India — the Twilio path could carry it with a `dtmf` field added to
`create_sip_participant()`.

### Not viable

Meet Media API alone (receive-only, and every participant must be preview-enrolled); Add-ons SDK
(no audio, needs a human browser session); Pexip SIP interop (needs a licensed Pexip Infinity
deployment, which is neither open source nor cheap, and is a video-endpoint gateway rather than a
bot substrate); MeetingBaas open source (join and speak are in separate, non-combinable repos);
LemonSlice (closed hosted relay).

### One hybrid worth remembering

If the meeting is inside a single Workspace we control and every participant can be preview-enrolled,
the Media API is a *better listener* than a browser bot: real SRTP audio, three streams of the
loudest speakers, no scraping. It would have to be paired with a browser bot or a dial-in leg purely
for the speaking direction, and the preview gating means it cannot be a product feature today. File
it under "revisit if the Media API goes GA and grows a send path."

---

## What we could not verify from a primary source

Consolidated from the sections above.

- Whether a Meet Media API client occupies a named roster entry and appears in
  `conferenceRecords.participants`. No primary doc states it either way.
- Any documented cap on concurrent Media API clients per conference or per project.
- Any explicit Google statement permitting or forbidding automated/unattended clients as a named
  category, and any Meet-specific recording-consent legal requirement beyond the in-product
  notification behaviour.
- An explicit primary sentence saying the Add-ons SDK cannot access audio — only the absence of any
  grant, plus Google's surface index assigning media to the Media API.
- Any explicit primary statement that headless Chrome cannot capture or produce WebRTC audio.
  Inferred from both production projects running headful under Xvfb.
- The Meet dial-in PIN's digit count; the exact behaviour of the "press 1" prompt; whether a
  phone-only participant can hold a meeting open before a host joins; whether dial-in participants
  are documented as barred from chat and captions specifically (only "audio-only access"); any cap
  on phone participants specifically.
- Whether India ever gets a local dial-in number for a tenant billed *outside* India. The docs list
  India under Global Dialing dial-in but never state the caller-side restriction.
- Whether Exotel or Twilio will carry an international outbound call to a foreign Meet dial-in
  number, and at what cost and quality. Outside Google's docs; not investigated.
- Whether Attendee's `/speech` and `output_audio` behave identically on all three platforms. The
  docs use Meet URLs throughout and list Speech as a generic bot capability, but there is no
  per-platform support matrix.
- Whether ELv2's licence-key clause is or will be enforced. No key-check code exists in Attendee's
  repo tree today.
- The minimum Chrome version for `--auto-accept-camera-and-microphone-capture`. Present in current
  `main`; ship version not determined.
- `peter.sh/chromium-command-line-switches` was not usable as a source (1,567 switches, too large to
  fetch); Chromium's `.cc` sources were read instead, which is the stronger source. Likewise the
  freedesktop PulseAudio wiki returns 403 behind an anti-bot challenge, so the module C sources were
  used.
- Pexip's total interop participant cap per deployment. Only per-call limits are documented.
- Cisco/Polycom-specific official interop pages were not reached. Google's own pages cover
  standards-based SIP/H.323 generically and require Pexip in all cases.
