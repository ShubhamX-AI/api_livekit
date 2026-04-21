# Get Assistant Details

Fetch full configuration for one assistant.

- **URL**: `/assistant/details/{assistant_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

## Path Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `assistant_id` | string | Assistant UUID. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Human-readable message. |
| `data.assistant_id` | string | Assistant UUID. |
| `data.assistant_name` | string | Assistant name. |
| `data.assistant_description` | string | Assistant description. |
| `data.assistant_prompt` | string | System prompt. |
| `data.assistant_llm_mode` | string | `pipeline` or `realtime`. |
| `data.assistant_llm_config` | object/null | Realtime LLM config. API key is masked when present. |
| `data.assistant_tts_model` | string/null | TTS provider in pipeline mode. |
| `data.assistant_tts_config` | object/null | TTS config. API key is masked when present. |
| `data.assistant_start_instruction` | string/null | Start instruction. |
| `data.assistant_interaction_config` | object | Interaction settings. |
| `data.assistant_end_call_enabled` | boolean | End-call tool flag. |
| `data.assistant_end_call_trigger_phrase` | string/null | End-call trigger phrase. |
| `data.assistant_end_call_agent_message` | string/null | End-call agent message. |
| `data.assistant_end_call_url` | string/null | End-call webhook URL. |
| `data.tool_ids` | array | Attached tool IDs. |
| `data.assistant_created_at` | string | Created timestamp (ISO-8601). |
| `data.assistant_updated_at` | string | Updated timestamp (ISO-8601). |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Assistant details retrieved. |
| 401 | Unauthorized. |
| 404 | Assistant not found or inactive. |
| 500 | Internal server error. |

## Example Response

```json
{
  "success": true,
  "message": "Assistant details retrieved successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Gemini Assistant",
    "assistant_description": "Realtime voice assistant",
    "assistant_prompt": "You are a helpful assistant.",
    "assistant_llm_mode": "realtime",
    "assistant_llm_config": {
      "provider": "gemini",
      "model": "gemini-3.1-flash-live-preview",
      "voice": "Puck",
      "api_key": "Using System provided API Key"
    },
    "assistant_tts_model": null,
    "assistant_tts_config": null,
    "assistant_start_instruction": null,
    "assistant_interaction_config": {
      "speaks_first": true,
      "filler_words": false,
      "silence_reprompts": false,
      "silence_reprompt_interval": 10.0,
      "silence_max_reprompts": 2,
      "background_sound_enabled": true,
      "thinking_sound_enabled": true,
      "allow_interruptions": false
    },
    "assistant_end_call_enabled": false,
    "assistant_end_call_trigger_phrase": null,
    "assistant_end_call_agent_message": null,
    "assistant_end_call_url": null,
    "tool_ids": [],
    "assistant_created_at": "2026-03-30T10:00:00.000000",
    "assistant_updated_at": "2026-03-30T10:00:00.000000"
  }
}
```
