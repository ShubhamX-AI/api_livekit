# Getting Started

## Overview

Choose the path that matches your use case:

- [Outbound SIP Call](#path-a-outbound-sip-call) - queue a phone call via Twilio or Exotel
- [Web Call](#path-b-web-call) - embed voice/chat in a browser or mobile app, no SIP required
- [Inbound Call](#path-c-inbound-call) - route incoming calls to an assistant
- [End-to-End Example](#end-to-end-example-outbound-call-with-a-tool-and-webhook) - full walkthrough from zero to receiving a webhook

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

Both modes support `assistant_interaction_config.speaks_first=true`. When enabled, the assistant sends an opening response using `assistant_start_instruction` (or its default greeting if omitted).

### Example A: Create Assistant in `pipeline` mode

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Support Bot",
    "assistant_description": "Customer support agent",
    "assistant_prompt": "You are a helpful support agent.",
    "assistant_start_instruction": "Hello, thanks for calling support. How can I help you today?",
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
    "assistant_start_instruction": "Hi, you're connected to Gemini Voice Bot. How can I assist you today?",
    "assistant_llm_mode": "realtime",
    "assistant_llm_config": {
      "provider": "gemini",
      "model": "gemini-3.1-flash-live-preview",
      "voice": "Puck"
    },
    "assistant_interaction_config": {
      "speaks_first": true,
      "silence_reprompts": true
    }
  }'
```

Save the `assistant_id` from the response.

Behavior note:
- `pipeline` mode sends the opening response through the pipeline path (LLM + configured TTS).
- `realtime` mode sends the opening response through the realtime conversation path.

## Step 3 (Optional) - Give Your Assistant Tools

Tools let the assistant call external APIs or return static data during a conversation. You can skip this step and add tools later.

### Create a tool

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_order_status",
    "tool_description": "Look up the current status of a customer order by order ID",
    "tool_parameters": [
      {
        "name": "order_id",
        "type": "string",
        "description": "The order ID to look up",
        "required": true
      }
    ],
    "tool_execution_type": "webhook",
    "tool_execution_config": {
      "url": "https://your-api.com/orders/status",
      "timeout": 5
    }
  }'
```

Save the `tool_id` from the response.

### Attach the tool to your assistant

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/attach/ASSISTANT_ID" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_ids": ["TOOL_ID"]
  }'
```

The assistant will now use this tool whenever the conversation requires it. See [Tools](api/tools/index.md) for full details.

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

    A `202 Accepted` response means the request was queued successfully. Save the returned `queue_id`.

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

    A `202 Accepted` response means the request was queued successfully. Save the returned `queue_id`.

Example response:

```json
{
  "success": true,
  "message": "Outbound call queued successfully",
  "data": {
    "queue_id": "QUEUE_ID",
    "status": "queued"
  }
}
```

### A3 - Check Queue Status

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/call/queue/QUEUE_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Use this endpoint to see whether the request is still `pending`, currently `dispatching`, already `dispatched`, or permanently `failed`.

### A4 - Track the Final Call Outcome

Once the queue item becomes `dispatched`, track the live call outcome through:

- the assistant end-call webhook (`assistant_end_call_url`)
- `GET /assistant/call-logs/{assistant_id}`

The final outcome (`answered`, `completed`, `busy`, `no_answer`, and so on) is not stored on the queue item itself.

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

## End-to-End Example: Outbound Call with a Tool and Webhook

This walkthrough covers every step from zero to receiving a post-call webhook with transcripts.

### 1. Create your API key

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "Demo User", "user_email": "demo@example.com"}'
```

Copy the `api_key` from the response. All commands below use it as `YOUR_API_KEY`.

### 2. Create an assistant with an end-call webhook

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Order Support",
    "assistant_description": "Helps customers check order status",
    "assistant_prompt": "You are a support agent for Acme Corp. Help the customer with their order. The customer name is {{name}}.",
    "assistant_llm_mode": "pipeline",
    "assistant_tts_model": "cartesia",
    "assistant_tts_config": {"voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"},
    "assistant_interaction_config": {"speaks_first": true, "silence_reprompts": true},
    "assistant_end_call_enabled": true,
    "assistant_end_call_trigger_phrase": "end the call",
    "assistant_end_call_agent_message": "Thank you for calling, goodbye!",
    "assistant_end_call_url": "https://your-server.com/webhook/call-ended"
  }'
```

Note the `assistant_id`.

### 3. Create a tool and attach it

```bash
# Create the tool
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "check_order",
    "tool_description": "Look up order status by order ID. Use when the customer asks about an order.",
    "tool_parameters": [{"name": "order_id", "type": "string", "required": true}],
    "tool_execution_type": "webhook",
    "tool_execution_config": {"url": "https://your-api.com/orders/lookup"}
  }'

# Attach it to the assistant
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/attach/ASSISTANT_ID" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool_ids": ["TOOL_ID"]}'
```

### 4. Create a SIP trunk

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "trunk_name": "My Twilio Trunk",
    "trunk_address": "your-sip-domain.sip.twilio.com",
    "trunk_numbers": ["+15550100000"],
    "trunk_auth_username": "your_username",
    "trunk_auth_password": "your_password",
    "trunk_type": "twilio"
  }'
```

Note the `trunk_id`.

### 5. Trigger the call

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID",
    "trunk_id": "TRUNK_ID",
    "to_number": "+15550200000",
    "call_service": "twilio",
    "metadata": {"name": "John Doe"}
  }'
```

The assistant will call the number, greet "John Doe" using the placeholder, and use the `check_order` tool if the customer asks about an order.

### 6. Receive the webhook

When the call ends, your `assistant_end_call_url` receives a POST with the full call record including transcripts, duration, recording URL, and token usage. See [End Call Webhook](api/calls/webhook.md) for the complete payload schema.

---

## Next Steps

- [Architecture](architecture.md) - full call-flow diagrams for all integration modes
- [Assistant APIs](api/assistant/index.md) - pipeline/realtime configuration, interaction settings, end-call tool
- [TTS Humanization Guide](api/assistant/tts-humanization.md) - write better spoken prompts
- [Tools APIs](api/tools/index.md) - give the assistant the ability to call external APIs
- [SIP Provider Setup](api/sip/providers.md) - Twilio and Exotel configuration details
