# Update Assistant

Update an existing assistant. Only send fields you want to change.

- **URL**: `/assistant/update/{assistant_id}`
- **Method**: `PATCH`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

## Path Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `assistant_id` | string | Assistant UUID. |

## Request Body (Common Fields)

| Field | Type | Description |
| :--- | :--- | :--- |
| `assistant_name` | string | New assistant name. |
| `assistant_description` | string | New assistant description. |
| `assistant_prompt` | string | New system prompt. |
| `assistant_llm_mode` | string | Target mode: `pipeline` or `realtime`. |
| `assistant_start_instruction` | string | New opening response text used when `assistant_interaction_config.speaks_first=true`. |
| `assistant_interaction_config` | object | Partial interaction-config update. |
| `assistant_end_call_enabled` | boolean | Enable or disable end-call tool. |
| `assistant_end_call_trigger_phrase` | string | End-call trigger phrase. |
| `assistant_end_call_agent_message` | string | End-call agent message. |
| `assistant_end_call_url` | string | End-call webhook URL. |

---

## Switching Modes

=== ":material-pipe: Switch to Pipeline"

    When switching to `pipeline` mode, you **must** provide both TTS fields in the same request.

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_llm_mode` | string | Yes | Set to `pipeline`. |
    | `assistant_tts_model` | string | Yes | One of `cartesia`, `sarvam`, `elevenlabs`, `mistral`. |
    | `assistant_tts_config` | object | Yes | TTS config for the selected provider. |

    **Example request**

    ```bash
    curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_llm_mode": "pipeline",
        "assistant_tts_model": "elevenlabs",
        "assistant_tts_config": {
          "voice_id": "JBFqnCBv7z4s9ByuOnH"
        }
      }'
    ```

=== ":material-lightning-bolt: Switch to Realtime"

    When switching to `realtime` mode, you **must** provide the LLM config.

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_llm_mode` | string | Yes | Set to `realtime`. |
    | `assistant_llm_config` | object | Yes | Realtime provider config (`provider`, `model`, `voice`, optional `api_key`). |

    **Example request**

    ```bash
    curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_llm_mode": "realtime",
        "assistant_llm_config": {
          "provider": "gemini",
          "model": "gemini-3.1-flash-live-preview",
          "voice": "Puck"
        }
      }'
    ```

---

## Validation Rules

- TTS fields must come in pairs: send both `assistant_tts_model` and `assistant_tts_config`, or neither.
- Switching to `realtime` requires `assistant_llm_config`.
- Switching to `pipeline` requires both `assistant_tts_model` and `assistant_tts_config`.

## Runtime Behavior Notes

- `assistant_interaction_config.speaks_first` is supported in both `pipeline` and `realtime` modes.
- When `speaks_first=true`, `assistant_start_instruction` is used as the opening response.
- `assistant_interaction_config.background_sound_enabled` controls background ambience for all sessions using the assistant.
- `assistant_interaction_config.thinking_sound_enabled` controls the typing-style thinking sound for all sessions using the assistant.
- `assistant_interaction_config.allow_interruptions` controls whether users can interrupt the assistant's initial greeting. Default: `false`.
- Partial `assistant_interaction_config` updates are merged with the stored config; omitted fields are preserved.
- Call-trigger APIs do not provide per-call overrides for these sound settings.

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Human-readable message. |
| `data.assistant_id` | string | Updated assistant UUID. |

## Example Response

```json
{
  "success": true,
  "message": "Assistant updated successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Assistant updated successfully. |
| 400 | Validation or payload mismatch error. |
| 401 | Unauthorized. |
| 404 | Assistant not found. |
| 500 | Internal server error. |
