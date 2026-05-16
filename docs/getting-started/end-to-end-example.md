# End-to-End Example

A full walkthrough from zero to receiving a post-call webhook with transcripts — outbound call, custom tool, end-call webhook.

## 1. Create your API key

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "Demo User", "user_email": "demo@example.com"}'
```

Copy the `api_key` from the response. All commands below use it as `YOUR_API_KEY`.

## 2. Create an assistant with an end-call webhook

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

## 3. Create a tool and attach it

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

## 4. Create a SIP trunk

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

## 5. Trigger the call

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

## 6. Receive the webhook

When the call ends, your `assistant_end_call_url` receives a POST with the full call record including transcripts, duration, recording URL, and token usage. See [End Call Webhook](../api/calls/webhook.md) for the complete payload schema.

---

## Next Steps

- [Architecture](../architecture/index.md) — full call-flow diagrams for all integration modes
- [Assistant APIs](../api/assistant/index.md) — pipeline/realtime configuration, interaction settings, end-call tool
- [TTS Humanization Guide](../api/assistant/tts-humanization.md) — write better spoken prompts
- [Tools APIs](../api/tools/index.md) — give the assistant the ability to call external APIs
- [SIP Provider Setup](../api/sip/providers.md) — Twilio and Exotel configuration details
