# Getting Started

## Overview

This quick start walks through creating an API key, creating an assistant, creating a SIP trunk, and placing a first outbound call.

## Prerequisites

- A deployed API base URL.
- LiveKit configured for your environment.
- Valid credentials for the SIP provider you will use.

## Quick Start

### 1. Create an API Key

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Admin User",
    "user_email": "admin@example.com"
  }'
```

### 2. Create an Assistant

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_name": "Support Bot",
    "assistant_description": "Customer support agent",
    "assistant_prompt": "You are a helpful support agent.",
    "assistant_tts_model": "cartesia",
    "assistant_tts_config": {
      "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
    },
    "assistant_interaction_config": {
      "speaks_first": true,
      "filler_words": false,
      "silence_reprompts": true
    }
  }'
```

### 3. Create a SIP Trunk

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

Store the returned `trunk_id` for call initiation.

### 4. Trigger an Outbound Call

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

## Next Steps

- Review [Architecture](architecture.md) for integration patterns.
- Use [Assistant APIs](api/assistant/index.md) to tune behavior.
- Use [Tools APIs](api/tools/index.md) to add external actions.
