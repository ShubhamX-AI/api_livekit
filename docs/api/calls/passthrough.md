# Passthrough Calls (Web ↔ SIP, No AI Agent)

Passthrough mode lets a human web user speak directly to a phone caller over SIP — with **no AI agent involved**. No STT, no LLM, no TTS. Just raw audio: web mic → SIP → mobile and mobile → SIP → web speaker.

Use this when you need a live human agent on the web side to handle calls through your existing SIP trunk.

---

## Prerequisites

- An active outbound trunk (`twilio` or `exotel`) with `passthrough_mode: true`
- Your LiveKit server URL (from your `.env` or dashboard)
- A web client that can connect to LiveKit — browser using [LiveKit JS SDK](https://docs.livekit.io/client-sdk-js/), React SDK, or any LiveKit client SDK

---

## Step 1 — Create a Passthrough-Enabled Trunk

Set `passthrough_mode: true` when creating the trunk. Optionally set `passthrough_webhook_url` to receive end-of-call notifications.

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
         -H "Content-Type: application/json" \
         -H "Authorization: Bearer <your_api_key>" \
         -d '{
               "trunk_name": "Human Agent Trunk (Twilio)",
               "trunk_type": "twilio",
               "trunk_config": {
                 "address": "example.pstn.twilio.com",
                 "numbers": ["+15550100000"],
                 "username": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                 "password": "your_auth_token_here"
               },
               "passthrough_mode": true,
               "passthrough_webhook_url": "https://your-app.com/webhooks/call-ended"
             }'
    ```

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
         -H "Content-Type: application/json" \
         -H "Authorization: Bearer <your_api_key>" \
         -d '{
               "trunk_name": "Human Agent Trunk (Exotel)",
               "trunk_type": "exotel",
               "trunk_config": {
                 "exotel_number": "+918044319240"
               },
               "passthrough_mode": true,
               "passthrough_webhook_url": "https://your-app.com/webhooks/call-ended"
             }'
    ```

**Response (both providers):**

```json
{
  "success": true,
  "message": "Outbound trunk created successfully, Store the trunk id securely.",
  "data": {
    "trunk_id": "ST_a1b2c3d4e5f6..."
  }
}
```

Save the `trunk_id` — you'll use it in every passthrough call request.

!!! warning "Passthrough is fixed at trunk creation time"
    `passthrough_mode` cannot be changed after creation. To switch, create a new trunk.
    A trunk with `passthrough_mode: true` **only** works with `POST /call/outbound_passthrough`.
    Normal AI calls (`POST /call/outbound`) require a trunk with `passthrough_mode: false` (default).

---

## Step 2 — Trigger the Passthrough Call

Call `POST /call/outbound_passthrough` from your server. The API creates a LiveKit room **synchronously** and returns a `room_token` immediately — so your web client can connect and be ready before the SIP call even starts ringing.

- **URL**: `/call/outbound_passthrough`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field       | Type   | Required | Description                                         |
| :---------- | :----- | :------- | :-------------------------------------------------- |
| `trunk_id`  | string | Yes      | ID of a passthrough-enabled trunk (`ST_...`).       |
| `to_number` | string | Yes      | Phone number to call in E.164 format.               |
| `metadata`  | object | No       | Optional key-value pairs stored on the call record. |

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound_passthrough" \
         -H "Content-Type: application/json" \
         -H "Authorization: Bearer <your_api_key>" \
         -d '{
               "trunk_id": "ST_a1b2c3d4e5f6...",
               "to_number": "+15550200000",
               "metadata": { "agent_name": "John", "ticket_id": "TKT-001" }
             }'
    ```

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound_passthrough" \
         -H "Content-Type: application/json" \
         -H "Authorization: Bearer <your_api_key>" \
         -d '{
               "trunk_id": "ST_exotel_abc123...",
               "to_number": "+918099990000",
               "metadata": { "agent_name": "Ravi", "ticket_id": "TKT-042" }
             }'
    ```

### Response

```json
{
  "success": true,
  "message": "Passthrough call queued successfully",
  "data": {
    "queue_id": "8b7df5ea0fdc497ea4f44bd31954a387",
    "room_name": "passthrough_abc123def456",
    "room_token": "<livekit-jwt>",
    "status": "queued"
  }
}
```

| Field        | What it is                                                             | What to do with it                                      |
| :----------- | :--------------------------------------------------------------------- | :------------------------------------------------------ |
| `queue_id`   | Identifier for this queue item                                         | Poll `GET /call/queue/{queue_id}` for dispatch status   |
| `room_name`  | LiveKit room the SIP bridge will join                                  | Store it — pass to your web client if needed            |
| `room_token` | Signed JWT that lets your web user join the LiveKit room               | **Pass this to your web client immediately**            |
| `status`     | Always `queued` at this point                                          | SIP dial happens in the background via the dispatcher   |

!!! info "Why is the token returned synchronously?"
    Normal outbound calls queue the room creation too — you never get a token upfront.
    Passthrough is different: the web user must be able to connect to LiveKit *before* the phone rings.
    So the API creates the room right away and returns the token in the same response.
    The SIP dial still happens asynchronously through the dispatcher.

---

## Step 3 — Connect Your Web Client and Talk

Take the `room_token` from Step 2 and use it to connect your web browser to LiveKit. Once connected:

- Your **mic audio** is automatically routed to the SIP caller
- The **SIP caller's audio** comes back as a remote audio track you subscribe to

### What the web user experiences

```
Before SIP answers   → Web user is connected to LiveKit room, but hears silence (no one else yet)
SIP dial in progress → Dispatcher dials the number in the background (~1-3 seconds after queue insert)
Phone ringing        → SIP bridge has joined the room; ringing audio comes through if provider sends ringback
SIP answered         → Mobile caller's audio appears as a remote track; bidirectional audio begins
Call ended           → Remote track removed; web user's mic is still live until they disconnect
```

### LiveKit JS SDK (browser)

```javascript
import { Room, RoomEvent, Track } from "livekit-client";

const LIVEKIT_URL = "wss://your-livekit-server.com"; // from your .env LIVEKIT_URL

async function startPassthroughCall(roomToken) {
  const room = new Room();

  // When the SIP bridge joins and publishes audio, attach it to a speaker
  room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === Track.Kind.Audio) {
      const audioEl = track.attach();
      audioEl.autoplay = true;
      document.body.appendChild(audioEl);
      console.log("SIP audio connected — call is live");
    }
  });

  // Optional: detect when SIP bridge leaves (call ended on phone side)
  room.on(RoomEvent.ParticipantDisconnected, (participant) => {
    console.log("Remote participant left — call may have ended");
  });

  // Connect to the LiveKit room with the token from /call/outbound_passthrough
  await room.connect(LIVEKIT_URL, roomToken);

  // Enable mic — everything you say goes to the SIP caller
  await room.localParticipant.setMicrophoneEnabled(true);

  console.log("Connected to room. Waiting for SIP call to be answered...");

  // Return room handle so caller can disconnect later
  return room;
}

// Usage:
const response = await fetch("/call/outbound_passthrough", { method: "POST", ... });
const { data } = await response.json();

const room = await startPassthroughCall(data.room_token);

// To hang up from the web side:
// await room.disconnect();
```

### React SDK

```jsx
import { LiveKitRoom, useLocalParticipant, useTracks } from "@livekit/components-react";
import { Track } from "livekit-client";

function PassthroughCall({ roomToken, livekitUrl }) {
  return (
    <LiveKitRoom
      token={roomToken}
      serverUrl={livekitUrl}
      audio={true}   // auto-publishes mic
      video={false}
    >
      <CallUI />
    </LiveKitRoom>
  );
}

function CallUI() {
  // Subscribe to all audio tracks (the SIP caller's audio will appear here)
  const tracks = useTracks([Track.Source.Microphone], { onlySubscribed: true });

  return (
    <div>
      <p>Call active — {tracks.length} remote audio track(s)</p>
      {tracks.map((track) => (
        <audio key={track.publication.trackSid} ref={(el) => el && track.publication.track?.attach(el)} autoPlay />
      ))}
    </div>
  );
}
```

!!! note "Audio permissions"
    The browser must have microphone permission granted before calling `setMicrophoneEnabled(true)`.
    Request permission early (before or during the call setup UI) to avoid delays.

---

## Step 4 — Monitor Call Dispatch State

Poll `GET /call/queue/{queue_id}` to confirm the dispatcher picked up the call:

=== "Twilio"

    ```bash
    curl "https://api-livekit-vyom.indusnettechnologies.com/call/queue/8b7df5ea0fdc497ea4f44bd31954a387" \
         -H "Authorization: Bearer <your_api_key>"
    ```

    ```json
    {
      "success": true,
      "message": "Queue status retrieved",
      "data": {
        "queue_id": "8b7df5ea0fdc497ea4f44bd31954a387",
        "status": "dispatched",
        "to_number": "+15550200000",
        "call_service": "twilio",
        "queued_at": "2024-01-15T10:00:00.000Z",
        "dispatched_at": "2024-01-15T10:00:02.000Z",
        "retry_count": 0,
        "last_error": null
      }
    }
    ```

=== "Exotel"

    ```bash
    curl "https://api-livekit-vyom.indusnettechnologies.com/call/queue/9c1ad10ef9b6484aad8e8d15a299f4b8" \
         -H "Authorization: Bearer <your_api_key>"
    ```

    ```json
    {
      "success": true,
      "message": "Queue status retrieved",
      "data": {
        "queue_id": "9c1ad10ef9b6484aad8e8d15a299f4b8",
        "status": "dispatched",
        "to_number": "+918099990000",
        "call_service": "exotel",
        "queued_at": "2024-01-15T10:00:00.000Z",
        "dispatched_at": "2024-01-15T10:00:01.000Z",
        "retry_count": 0,
        "last_error": null
      }
    }
    ```

Queue state lifecycle: `pending → dispatching → dispatched` or `failed`.

`dispatched` means the SIP bridge has started dialling. The phone is now ringing (or already answered).

---

## Step 5 — Receive the End-of-Call Webhook

If `passthrough_webhook_url` is set on the trunk, a POST fires on **every terminal outcome**.

=== "Twilio — Completed"

    ```json
    {
      "success": true,
      "message": "Call details fetched successfully",
      "data": {
        "room_name": "passthrough_abc123def456",
        "queue_id": "8b7df5ea0fdc497ea4f44bd31954a387",
        "assistant_id": null,
        "assistant_name": null,
        "is_passthrough": true,
        "to_number": "+15550200000",
        "call_status": "completed",
        "call_status_reason": null,
        "answered_at": "2024-01-15T10:00:05.000Z",
        "recording_path": "https://your-bucket.s3.amazonaws.com/recordings/passthrough_abc123.ogg",
        "transcripts": [],
        "started_at": "2024-01-15T10:00:00.000Z",
        "ended_at": "2024-01-15T10:05:30.000Z",
        "call_duration_minutes": 5.42,
        "billable_duration_minutes": 6,
        "call_type": "outbound",
        "call_service": "twilio",
        "platform_number": "+15550100000"
      }
    }
    ```

=== "Exotel — Completed"

    ```json
    {
      "success": true,
      "message": "Call details fetched successfully",
      "data": {
        "room_name": "passthrough_xyz789abc123",
        "queue_id": "9c1ad10ef9b6484aad8e8d15a299f4b8",
        "assistant_id": null,
        "assistant_name": null,
        "is_passthrough": true,
        "to_number": "+918099990000",
        "call_status": "completed",
        "call_status_reason": null,
        "answered_at": "2024-01-15T10:00:04.000Z",
        "recording_path": "https://your-bucket.s3.amazonaws.com/recordings/passthrough_xyz789.ogg",
        "transcripts": [],
        "started_at": "2024-01-15T10:00:00.000Z",
        "ended_at": "2024-01-15T10:03:45.000Z",
        "call_duration_minutes": 3.68,
        "billable_duration_minutes": 4,
        "call_type": "outbound",
        "call_service": "exotel",
        "platform_number": "+918044319240"
      }
    }
    ```

=== "Busy / No Answer"

    ```json
    {
      "success": true,
      "message": "Call details fetched successfully",
      "data": {
        "room_name": "passthrough_abc123def456",
        "queue_id": "8b7df5ea0fdc497ea4f44bd31954a387",
        "assistant_id": null,
        "assistant_name": null,
        "is_passthrough": true,
        "to_number": "+15550200000",
        "call_status": "busy",
        "call_status_reason": "SIP 486 Busy Here",
        "sip_status_code": 486,
        "sip_status_text": "Busy Here",
        "answered_at": null,
        "recording_path": null,
        "transcripts": [],
        "started_at": "2024-01-15T10:00:00.000Z",
        "ended_at": "2024-01-15T10:00:08.000Z",
        "call_duration_minutes": 0,
        "billable_duration_minutes": 0,
        "call_type": "outbound",
        "call_service": "twilio",
        "platform_number": "+15550100000"
      }
    }
    ```

!!! note "Passthrough webhook vs AI call webhook"
    - `assistant_id` and `assistant_name` are always `null`
    - `transcripts` is always `[]` — no STT
    - `is_passthrough: true` — use to identify passthrough records
    - `usage` field is absent — no LLM/TTS consumed
    - Webhook fires on **all** outcomes including `busy`, `no_answer`, `timeout`, `failed`
    - `call_duration_minutes` measured from `answered_at` (not `started_at`) so ringing time is excluded

---

## Get Call Records

```bash
# All passthrough calls
curl "https://api-livekit-vyom.indusnettechnologies.com/call/records?passthrough_only=true" \
     -H "Authorization: Bearer <your_api_key>"

# Filter by number
curl "https://api-livekit-vyom.indusnettechnologies.com/call/records?to_number=%2B918099990000" \
     -H "Authorization: Bearer <your_api_key>"

# Filter by status, page 2
curl "https://api-livekit-vyom.indusnettechnologies.com/call/records?passthrough_only=true&call_status=completed&limit=20&page=2" \
     -H "Authorization: Bearer <your_api_key>"

# Sort by duration descending
curl "https://api-livekit-vyom.indusnettechnologies.com/call/records?sort_by=call_duration_minutes&sort_order=desc" \
     -H "Authorization: Bearer <your_api_key>"
```

### Query Parameters

| Parameter          | Type     | Default      | Description                                                   |
| :----------------- | :------- | :----------- | :------------------------------------------------------------ |
| `passthrough_only` | boolean  | `false`      | Returns only passthrough calls when `true`                    |
| `to_number`        | string   | —            | Filter by destination phone number (E.164)                    |
| `call_status`      | string   | —            | `completed`, `failed`, `busy`, `no_answer`, `timeout`         |
| `start_date`       | datetime | —            | ISO 8601 start of date range (inclusive)                      |
| `end_date`         | datetime | —            | ISO 8601 end of date range (inclusive)                        |
| `sort_by`          | string   | `started_at` | Field to sort by: `started_at`, `ended_at`, `call_duration_minutes` |
| `sort_order`       | string   | `desc`       | `asc` or `desc`                                               |
| `page`             | integer  | `1`          | Page number (minimum: 1)                                      |
| `limit`            | integer  | `10`         | Items per page (1–100)                                        |

### Response Pagination

```json
{
  "data": {
    "records": [...],
    "pagination": {
      "total": 42,
      "page": 1,
      "limit": 10,
      "total_pages": 5
    }
  }
}
```

Every record includes `"is_passthrough": true` so call type is always identifiable even in mixed (non-filtered) queries.

---

## Error Handling

All SIP errors fire the webhook and update `CallRecord`:

| Outcome     | `call_status` | Cause                               |
| :---------- | :------------ | :---------------------------------- |
| SIP 486/600 | `busy`        | Callee line is busy                 |
| SIP 408/480 | `no_answer`   | Callee did not answer               |
| 60s timeout | `timeout`     | SIP setup timed out before answer   |
| SIP 403/603 | `rejected`    | Callee/provider rejected            |
| Other error | `failed`      | Generic SIP failure or bridge crash |

---

## Limitations

| Feature             | Status                                                                                           |
| :------------------ | :----------------------------------------------------------------------------------------------- |
| Transcript          | Not available — no STT runs                                                                      |
| Hold detection      | Hold events published to room but no action taken (no session.py)                                |
| Analytics           | Excluded from `/analytics/calls/by-assistant`; use `GET /call/records?passthrough_only=true`     |
| Twilio finalization | Relies on orphan reaper (30-min sweep) for crash/unexpected-disconnect cleanup                   |

---

## Full Flow Summary

```
1.  Create trunk: passthrough_mode=true, save trunk_id
2.  Server: POST /call/outbound_passthrough  →  { room_token, room_name, queue_id }
3.  Server → Web client: send room_token + LIVEKIT_URL
4.  Web client: connect LiveKit with room_token, enable mic
5.  Dispatcher: dials SIP (no agent dispatched), marks queue=dispatched
6.  SIP answered: audio flows web mic ↔ RTP bridge ↔ SIP ↔ mobile
7.  Call ends: CallRecord updated, recording saved, webhook POSTed
8.  GET /call/records?passthrough_only=true for history
```
