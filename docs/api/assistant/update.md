# Update Assistant

Update the configuration of an existing assistant.

- **URL**: `/assistant/update/{assistant_id}`
- **Method**: `PATCH`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter      | Type   | Description                          |
| :------------- | :----- | :----------------------------------- |
| `assistant_id` | string | The UUID of the assistant to update. |

### Request Body

Only provide the fields you want to update. All fields are optional.

!!! note "Important"

    If updating `assistant_tts_model` and `assistant_tts_config`, both should be updated together to ensure consistency.

| Field                         | Type   | Description                                       |
| :---------------------------- | :----- | :------------------------------------------------ |
| `assistant_name`              | string | The new name of the assistant (1-100 characters). |
| `assistant_description`       | string | The new description.                              |
| `assistant_prompt`            | string | The new system prompt.                            |
| `assistant_tts_model`         | string | The new TTS provider (`cartesia`, `sarvam`, `elevenlabs`, or `mistral`).|
| `assistant_tts_config`        | object | The new TTS configuration object.                 |
| `assistant_start_instruction` | string | The new start instruction.                        |
| `assistant_interaction_config` | object | New interaction configuration object. |
| `assistant_end_call_enabled` | boolean | Enable/disable built-in `end_call` tool. Default remains existing value; for new assistants, default is `false`. |
| `assistant_end_call_trigger_phrase` | string | Example user phrase that should trigger call end. If omitted, existing value is kept; when effective value is empty, generic confirmation-based trigger rule is used. |
| `assistant_end_call_agent_message` | string | What the assistant says before ending the call. If omitted, existing value is kept; when effective value is empty, fallback is `say goodbye to the user`. |
| `assistant_end_call_url`      | string | The new webhook URL.                              |

### Response Schema

| Field               | Type    | Description                                |
| :------------------ | :------ | :----------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful. |
| `message`           | string  | Human-readable success message.            |
| `data`              | object  | Contains the updated assistant ID.         |
| `data.assistant_id` | string  | The ID of the updated assistant.           |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Assistant updated successfully.       |
| 400  | Bad Request - Invalid input data.               |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 404  | Not Found - Assistant does not exist.           |
| 500  | Server Error - Internal server error.           |

### Interaction Configuration

When updating the interaction configuration, you only need to provide the fields you want to change.

| Field | Type | Description |
| :--- | :--- | :--- |
| `speaks_first` | boolean | If `true`, the assistant initiates the conversation. If `false`, it waits for the user to speak first. |
| `filler_words` | boolean | Enable or disable short filler phrases (like "Um", "Let me see"). |
| `silence_reprompts` | boolean | Enable or disable proactive speaking when the user is silent. |
| `silence_reprompt_interval` | number | The time in seconds to wait for user input before a reprompt (1.0 - 60.0). |
| `silence_max_reprompts` | number | The maximum number of times the assistant will reprompt (0 - 5). |

### Example: Update TTS Configuration

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_name": "Updated Support Bot",
           "assistant_tts_model": "sarvam",
           "assistant_tts_config": {
             "speaker": "meera",
             "target_language_code": "hi-IN"
           }
         }'
```

### Example: Update Interaction Config

You can update specific fields within the interaction configuration without affecting others.

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_interaction_config": {
             "filler_words": true,
             "speaks_first": false
           }
         }'
```

**Example: Update to ElevenLabs TTS**

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_tts_model": "elevenlabs",
           "assistant_tts_config": {
             "voice_id": "JBFqnCBv7z4s9ByuOnH"
           }
         }'
```

**Example: Update to Mistral TTS**

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_tts_model": "mistral",
           "assistant_tts_config": {
             "voice_id": "your_mistral_voice_id"
           }
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant updated successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```
