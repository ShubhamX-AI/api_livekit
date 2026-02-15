# Getting Started

## Next Steps

- Explore the [Architecture](architecture.md) to understand the system.
- Check out [Tool Usage](api/tools.md) to add functionality.

---

## Quick Start

### 1. Create Your First API Key

```bash
curl -X POST "http://localhost:8000/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Admin User",
    "user_email": "admin@example.com"
  }'
```

### 2. Create an Assistant

```bash
curl -X POST "http://localhost:8000/assistant/create" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Support Bot",
    "assistant_description": "Customer support agent",
    "assistant_prompt": "You are a helpful support agent.",
    "assistant_tts_model": "cartesia",
    "assistant_tts_config": {
      "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
    }
  }'
```

### 3. Create a SIP Trunk

Before you can make calls, you need to configure a SIP trunk (e.g., Twilio).

```bash
curl -X POST "http://localhost:8000/sip/create-outbound-trunk" \
  -H "x-api-key: YOUR_API_KEY" \
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

*Note: Store the returned `trunk_id` for the next step.*

### 4. Trigger an Outbound Call

```bash
curl -X POST "http://localhost:8000/call/outbound" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID",
    "trunk_id": "TRUNK_ID",
    "to_number": "+15550100000",
    "call_service": "twilio"
  }'
```
