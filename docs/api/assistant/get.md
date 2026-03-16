# Get Assistant Details

Fetch detailed information about a specific assistant.

- **URL**: `/assistant/details/{assistant_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter      | Type   | Description                |
| :------------- | :----- | :------------------------- |
| `assistant_id` | string | The UUID of the assistant. |

### Response Schema

| Field                              | Type    | Description                                |
| :--------------------------------- | :------ | :----------------------------------------- |
| `success`                          | boolean | Indicates if the operation was successful. |
| `message`                          | string  | Human-readable success message.            |
| `data`                             | object  | Complete assistant configuration.          |
| `data.assistant_id`                | string  | Unique identifier for the assistant.       |
| `data.assistant_name`              | string  | The name of the assistant.                 |
| `data.assistant_description`       | string  | The description of the assistant.          |
| `data.assistant_prompt`            | string  | The system prompt.                         |
| `data.assistant_tts_model`         | string  | The TTS provider.                          |
| `data.assistant_tts_config`        | object  | The TTS configuration object.              |
| `data.assistant_start_instruction` | string  | The start instruction (if set).            |
| `data.assistant_interaction_config` | object | Interaction settings for the assistant. |
| `data.assistant_end_call_enabled`  | boolean | Whether built-in end call behavior is enabled (`false` by default). |
| `data.assistant_end_call_trigger_phrase` | string | Example user phrase for end-call trigger. If `null`/empty, runtime uses generic confirmation-based trigger guidance. |
| `data.assistant_end_call_agent_message` | string | Assistant message spoken before ending call. If `null`/empty, runtime fallback is `say goodbye to the user`. |
| `data.assistant_end_call_url`      | string  | The webhook URL (if set).                  |
| `data.tool_ids`                    | array   | List of attached tool IDs.                 |
| `data.assistant_created_at`        | string  | ISO 8601 timestamp of creation.            |
| `data.assistant_updated_at`        | string  | ISO 8601 timestamp of last update.         |

### HTTP Status Codes

| Code | Description                                          |
| :--- | :--------------------------------------------------- |
| 200  | Success - Assistant details retrieved.               |
| 401  | Unauthorized - Invalid or missing Bearer token.      |
| 404  | Not Found - Assistant does not exist or is inactive. |
| 500  | Server Error - Internal server error.                |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/details/550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant details retrieved successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Bot",
    "assistant_description": "First line of support",
    "assistant_prompt": "You are a helpful customer support agent.",
    "assistant_tts_model": "cartesia",
    "assistant_tts_config": {
      "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
    },
    "assistant_start_instruction": null,
    "assistant_interaction_config": {
      "speaks_first": true,
      "filler_words": false,
      "silence_reprompts": false,
      "silence_reprompt_interval": 10.0,
      "silence_max_reprompts": 2
    },
    "assistant_end_call_enabled": true,
    "assistant_end_call_trigger_phrase": "Thanks, that's all. You can end the call now.",
    "assistant_end_call_agent_message": "Thank you for your time. Have a great day.",
    "assistant_end_call_url": null,
    "tool_ids": [],
    "assistant_created_at": "2024-01-15T10:00:00.000000",
    "assistant_updated_at": "2024-01-15T10:00:00.000000"
  }
}
```
