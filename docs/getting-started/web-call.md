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
