# Web Call

Web calls use WebRTC directly — no SIP trunk required. The client joins a LiveKit room in the browser or mobile app.

Prerequisite: complete [Step 1–3](index.md) to have an `assistant_id`.

## B1 — Generate a Token

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/get_token" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID"
  }'
```

The response contains a `token` and `room_name`. Pass the token to the LiveKit client SDK to join the room.

## B2 — Connect with LiveKit SDK

```ts
import { Room } from "livekit-client";

const room = new Room();
await room.connect("wss://your-livekit-server", token);
```

The assistant joins automatically once the room is created. Both audio and typed text input (`lk.chat` topic) are supported.

## B3 — Text-Only Chat (Optional)

To run the session as a pure text chatbot (no mic, no speaker, no recording, no TTS/STT bill), set `"text_only": true` on the token request:

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/get_token" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID",
    "text_only": true
  }'
```

The LLM still runs and emits text on the `lk.chat` topic for both client → agent and agent → client. Only pipeline-mode assistants are supported; realtime-mode assistants return HTTP 400. See [API reference → Text-Only Mode](../api/calls/web-call.md#text-only-mode-text_only-true) for details.
