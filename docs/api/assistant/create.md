# Create Assistant

Create a new AI assistant configuration.

- **URL**: `/assistant/create`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field                         | Type   | Required | Description                                                                       |
| :---------------------------- | :----- | :------- | :-------------------------------------------------------------------------------- |
| `assistant_name`              | string | Yes      | The name of the assistant (1-100 characters).                                     |
| `assistant_description`       | string | Yes      | A description of the assistant.                                                   |
| `assistant_prompt`            | string | Yes      | The system prompt that defines the assistant's behavior.                          |
| `assistant_tts_model`         | string | Yes      | The TTS provider. One of `cartesia`, `sarvam`, or `elevenlabs`.                   |
| `assistant_tts_config`        | object | Yes      | The TTS configuration object (see below).                                         |
| `assistant_start_instruction` | string | No       | Instruction for the assistant to speak when the call starts (max 200 characters). |
| `assistant_interaction_config` | object | No | Interaction settings (see below). |
| `assistant_end_call_enabled`  | boolean | No       | If `true`, enables built-in `end_call` tool for graceful call ending. Default: `false`. |
| `assistant_end_call_trigger_phrase` | string | No | Example user phrase that should signal the assistant to trigger `end_call` (max 300 chars). Default when omitted: generic instruction to end only after clear user confirmation. |
| `assistant_end_call_agent_message` | string | No | What the assistant should say just before ending the call (max 300 chars). Default when omitted: `say goodbye to the user`. |
| `assistant_end_call_url`      | string | No       | URL to POST call details when the call ends.                                      |

### Interaction Configuration

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `speaks_first` | boolean | No | If `true` (default), the assistant speaks first. If `false`, it stays silent and waits for the user to speak first. |
| `filler_words` | boolean | No | If `true`, the assistant generates short filler phrases while the user is speaking. Default: `false`. |
| `silence_reprompts` | boolean | No | If `true`, enables silence reprompts when the user stops responding. Default: `false`. |
| `silence_reprompt_interval` | number | No | Interval in seconds between silence reprompts (1.0 - 60.0). Default: `10.0`. |
| `silence_max_reprompts` | number | No | Maximum number of silence reprompts before ending the session (0 - 5). Default: `2`. |

!!! note "End call defaults"

    If `assistant_end_call_enabled` is not provided, it defaults to `false`.
    If enabled but `assistant_end_call_trigger_phrase` is not provided, the assistant uses a generic trigger rule (end only after clear user confirmation).
    If enabled but `assistant_end_call_agent_message` is not provided, the final message falls back to `say goodbye to the user`.

### TTS Configuration

=== "Cartesia Configuration"

    Use this when `assistant_tts_model` is set to `"cartesia"`.

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `voice_id` | string | Yes | The Cartesia voice ID (UUID format). |
    | `api_key` | string | No | Optional Cartesia API key. If not provided, the system's default key will be used. |

=== "Sarvam Configuration"

    Use this when `assistant_tts_model` is set to `"sarvam"`.

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `speaker` | string | Yes | The Sarvam speaker identifier (e.g., "meera", "arvind"). |
    | `target_language_code` | string | No | BCP-47 language code (default: "bn-IN"). |
    | `api_key` | string | No | Optional Sarvam API key. If not provided, the system's default key will be used. |

=== "ElevenLabs Configuration"

    Use this when `assistant_tts_model` is set to `"elevenlabs"`.

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `voice_id` | string | Yes | The ElevenLabs voice ID. |
    | `api_key` | string | No | Optional ElevenLabs API key. If not provided, the system's default key will be used. |

### Response Schema

| Field                 | Type    | Description                                 |
| :-------------------- | :------ | :------------------------------------------ |
| `success`             | boolean | Indicates if the operation was successful.  |
| `message`             | string  | Human-readable success message.             |
| `data`                | object  | Contains the created assistant details.     |
| `data.assistant_id`   | string  | Unique identifier for the assistant (UUID). |
| `data.assistant_name` | string  | The name of the assistant.                  |

### HTTP Status Codes

| Code | Description                                                       |
| :--- | :---------------------------------------------------------------- |
| 200  | Success - Assistant created successfully.                         |
| 400  | Bad Request - Invalid input data or mismatched TTS configuration. |
| 401  | Unauthorized - Invalid or missing Bearer token.                   |
| 500  | Server Error - Internal server error.                             |

### Example: Cartesia TTS

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
         -d '{
           "assistant_name": "Support Bot",
           "assistant_description": "First line of support",
           "assistant_prompt": "You are a helpful customer support agent.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
             "api_key": "your_custom_cartesia_api_key"
           }
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant created successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Bot"
  }
}
```

### Example: Sarvam TTS

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
         -d '{
           "assistant_name": "Hindi Support",
           "assistant_description": "Hindi speaking support agent",
           "assistant_prompt": "You are a helpful assistant who speaks Hindi.",
           "assistant_tts_model": "sarvam",
           "assistant_tts_config": {
             "speaker": "meera",
             "target_language_code": "hi-IN",
             "api_key": "your_custom_sarvam_api_key"
           }
         }'
```

### Example: ElevenLabs TTS

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
         -d '{
           "assistant_name": "Premium Voice Assistant",
           "assistant_description": "High-quality voice assistant",
           "assistant_prompt": "You are a helpful premium assistant.",
           "assistant_tts_model": "elevenlabs",
           "assistant_tts_config": {
             "voice_id": "JBFqnCBv7z4s9ByuOnH",
             "api_key": "your_custom_elevenlabs_api_key"
           }
         }'
```

### Example: With Start Instruction

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_name": "Sales Agent",
           "assistant_description": "Outbound sales representative",
           "assistant_prompt": "You are a friendly sales agent.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
           },
           "assistant_start_instruction": "Hello! I'\''m calling from Acme Corp. How are you today?",
           "assistant_interaction_config": {
             "speaks_first": true,
             "filler_words": true,
             "silence_reprompts": true
           },
           "assistant_end_call_enabled": true,
           "assistant_end_call_trigger_phrase": "Thanks, that's all. You can end the call now.",
           "assistant_end_call_agent_message": "Thank you for your time. Have a great day.",
           "assistant_end_call_url": "https://api.example.com/call-ended"
         }'
```

### Example: User Speaks First

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_name": "Passive Assistant",
           "assistant_description": "Waits for user input",
           "assistant_prompt": "You are a helpful assistant.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
           },
           "assistant_interaction_config": {
             "speaks_first": false
           }
         }'
```
