# List Assistants

List assistants created by the current user.

- **URL**: `/assistant/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

## Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `page` | integer | No | `1` | Page number (min 1). |
| `limit` | integer | No | `10` | Page size (1-100). |
| `assistant_name` | string | No | - | Case-insensitive partial name filter. |
| `start_date` | string | No | - | ISO-8601 lower bound for creation time. |
| `end_date` | string | No | - | ISO-8601 upper bound for creation time. |
| `sort_by` | string | No | `assistant_created_at` | Sort field. |
| `sort_order` | string | No | `desc` | `asc` or `desc`. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Human-readable message. |
| `data.assistants` | array | Assistant list. |
| `data.assistants[].assistant_id` | string | Assistant UUID. |
| `data.assistants[].assistant_name` | string | Assistant name. |
| `data.assistants[].assistant_llm_mode` | string | Assistant mode: `pipeline` or `realtime`. |
| `data.assistants[].assistant_tts_model` | string/null | TTS provider for pipeline assistants. |
| `data.assistants[].assistant_tts_config` | object/null | Masked TTS config. |
| `data.assistants[].assistant_interaction_config` | object | Interaction settings. |
| `data.assistants[].assistant_created_by_email` | string | Creator email. |
| `data.pagination.total` | integer | Total matching assistants. |
| `data.pagination.page` | integer | Current page. |
| `data.pagination.limit` | integer | Page size. |
| `data.pagination.total_pages` | integer | Total page count. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Assistants retrieved successfully. |
| 401 | Unauthorized. |
| 500 | Internal server error. |

## Example Response

```json
{
  "success": true,
  "message": "Assistants retrieved successfully",
  "data": {
    "assistants": [
      {
        "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
        "assistant_name": "Support Bot",
        "assistant_llm_mode": "pipeline",
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a16...275",
          "api_key": "Using System provided API Key"
        },
        "assistant_interaction_config": {
          "speaks_first": true,
          "filler_words": true,
          "silence_reprompts": true,
          "silence_reprompt_interval": 10.0,
          "silence_max_reprompts": 2,
          "background_sound_enabled": true,
          "thinking_sound_enabled": true,
          "allow_interruptions": false
        },
        "assistant_created_by_email": "admin@example.com"
      }
    ],
    "pagination": {
      "total": 1,
      "page": 1,
      "limit": 10,
      "total_pages": 1
    }
  }
}
```
