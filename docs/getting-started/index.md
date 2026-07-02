# Getting Started

Set up an API key, create your first assistant, and choose the integration path that matches your use case.

## Choose a Path

After completing the common setup below, pick one:

- [Outbound SIP Call](outbound-sip.md) — queue a phone call via Twilio or Exotel.
- [Web Call](web-call.md) — embed voice/chat in a browser or mobile app; no SIP trunk required.
- [Inbound Call](inbound.md) — route incoming calls to an assistant.
- [End-to-End Example](end-to-end-example.md) — full walkthrough from zero to receiving a webhook.

---

## Step 1 — Create an API Key

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Admin User",
    "user_email": "admin@example.com"
  }'
```

Save the `api_key` from the response. All subsequent requests require `Authorization: Bearer <api_key>`.

## Step 2 — Create an Assistant

Assistants support two execution modes:

Mode = output shape; `assistant_llm_config.provider` = LLM vendor (`openai` | `gemini`), honored in both modes.

- `pipeline` (default): LLM emits text, a separate TTS provider speaks it. Vendor `openai` (default) or `gemini`.
- `realtime`: LLM speaks its own audio (no external TTS). Vendor `gemini` (default) or `openai`.

LLM config rules:

- `pipeline`: `assistant_llm_config` is optional (defaults to `provider="openai"`). Set `gemini` to switch vendor; `api_key` overrides the selected vendor's system key.
- `realtime`: `assistant_llm_config` is required, but `provider`, `model`, and `voice` may be omitted to use defaults.
- Defaults — Gemini: `model="gemini-3.1-flash-live-preview"`, `voice="Puck"`; OpenAI realtime: `model="gpt-realtime-1.5"`, `voice="marin"`.

Both modes support `assistant_interaction_config.speaks_first=true`. When enabled, the assistant sends an opening response using `assistant_start_instruction` (or its default greeting if omitted).

### Example A — Create Assistant in `pipeline` mode

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
    "assistant_llm_config": {
      "api_key": "sk-..."
    },
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

### Example B — Create Assistant in `realtime` mode

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

Minimal realtime payload:

```json
{
  "assistant_llm_mode": "realtime",
  "assistant_llm_config": {}
}
```

Save the `assistant_id` from the response.

Behavior note:

- `pipeline` mode sends the opening response through the pipeline path (LLM + configured TTS).
- `realtime` mode sends the opening response through the realtime conversation path.

## Step 3 (Optional) — Give Your Assistant Tools

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

The assistant will now use this tool whenever the conversation requires it. See [Tools](../api/tools/index.md) for full details.

---

## Next

Pick your path:

- [Outbound SIP Call →](outbound-sip.md)
- [Web Call →](web-call.md)
- [Inbound Call →](inbound.md)
- [End-to-End Example →](end-to-end-example.md)
