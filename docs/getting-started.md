# Getting Started

## Overview

Choose the path that matches your use case:

- [Outbound SIP Call](#path-a-outbound-sip-call) - dial a phone number via Twilio or Exotel
- [Web Call](#path-b-web-call) - embed voice/chat in a browser or mobile app, no SIP required
- [Inbound Call](#path-c-inbound-call) - route incoming calls to an assistant

All paths start with the same first two steps.

---

## Step 1 - Create an API Key

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Admin User",
    "user_email": "admin@example.com"
  }'
```

Save the `api_key` from the response. All subsequent requests require `Authorization: Bearer <api_key>`.

## Step 2 - Create an Assistant

Assistants support two execution modes:

- `pipeline` (default): OpenAI realtime handles STT+LLM and a separate TTS provider speaks output.
- `realtime`: Gemini realtime handles STT+LLM+TTS in one model.

### Example A: Create Assistant in `pipeline` mode

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Support Bot",
    "assistant_description": "Customer support agent",
    "assistant_prompt": "You are a helpful support agent.",
    "assistant_llm_mode": "pipeline",
    "assistant_tts_model": "mistral",
    "assistant_tts_config": {
      "voice_id": "your_mistral_voice_id"
    },
    "assistant_interaction_config": {
      "speaks_first": true,
      "filler_words": false,
      "silence_reprompts": true
    }
  }'
```

### Example B: Create Assistant in `realtime` mode

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Gemini Voice Bot",
    "assistant_description": "Realtime conversational assistant",
    "assistant_prompt": "You are a helpful voice assistant.",
    "assistant_llm_mode": "realtime",
    "assistant_llm_config": {
      "provider": "gemini",
      "model": "gemini-3.1-flash-live-preview",
      "voice": "Puck"
    }
  }'
```

Save the `assistant_id` from the response.

---

## Path A: Outbound SIP Call

### A1 - Create a SIP Trunk

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "trunk_name": "My Twilio Trunk",
        "trunk_address": "your-twilio-sip-domain.sip.twilio.com",
        "trunk_numbers": ["+15550100000"],
        "trunk_auth_username": "your_twilio_username",
        "trunk_auth_password": "your_twilio_password",
        "trunk_type": "twilio"
      }'
    ```

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "trunk_name": "My Exotel Trunk",
        "trunk_type": "exotel",
        "trunk_config": {
          "exotel_number": "+918044319240"
        }
      }'
    ```

Save the `trunk_id` (format: `ST_...`) from the response.

### A2 - Trigger the Call

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "assistant_id": "ASSISTANT_ID",
        "trunk_id": "TRUNK_ID",
        "to_number": "+15550100000",
        "call_service": "twilio"
      }'
    ```

    A `200 OK` response means the call was placed successfully.

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "assistant_id": "ASSISTANT_ID",
        "trunk_id": "TRUNK_ID",
        "to_number": "+918044319240",
        "call_service": "exotel"
      }'
    ```

    A `202 Accepted` response means call setup has started. The final outcome (answered, busy, no_answer, etc.) is delivered asynchronously via the end-call webhook configured on the assistant (`assistant_end_call_url`).

Save the `room_name` from the response to correlate with webhook events and call logs.

---

## Path B: Web Call

Web calls use WebRTC directly - no SIP trunk required. The client joins a LiveKit room in the browser or mobile app.

### B1 - Generate a Token

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/get_token" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID"
  }'
```

The response contains a `token` and `room_name`. Pass the token to the LiveKit client SDK to join the room.

### B2 - Connect with LiveKit SDK

```ts
import { Room } from "livekit-client";

const room = new Room();
await room.connect("wss://your-livekit-server", token);
```

The assistant joins automatically once the room is created. Both audio and typed text input (`lk.chat` topic) are supported.

---

## Path C: Inbound Call

Inbound calls (Exotel only) route incoming calls to an assistant based on the dialed number.

### C1 - Assign an Inbound Number

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound/assign" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID",
    "service": "exotel",
    "inbound_config": {
      "phone_number": "+918044319240"
    }
  }'
```

When someone dials `+918044319240`, the assistant is automatically dispatched into a LiveKit room.

See [Inbound Calls](api/inbound/index.md) and [Inbound Context Strategies](api/inbound-context-strategy/index.md) for full details.

---

## Next Steps

- [Architecture](architecture.md) - full call-flow diagrams for all integration modes
- [Assistant APIs](api/assistant/index.md) - pipeline/realtime configuration, interaction settings, end-call tool
- [TTS Humanization Guide](api/assistant/tts-humanization.md) - write better spoken prompts
- [Tools APIs](api/tools/index.md) - give the assistant the ability to call external APIs
- [SIP Provider Setup](api/sip/providers.md) - Twilio and Exotel configuration details
