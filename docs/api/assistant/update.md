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

## LLM Config Rules

- In `pipeline` mode, `assistant_llm_config` is optional. Only `api_key` is used; `provider`, `model`, and `voice` are ignored.
- In `pipeline` mode, `assistant_llm_config.api_key` overrides the system `OPENAI_API_KEY`. Omit `assistant_llm_config` entirely to use the system key.
- You can update `assistant_llm_config` alone (without re-sending `assistant_llm_mode` or TTS fields) and the existing TTS config is preserved.
- In `realtime` mode, `assistant_llm_config` is required only when switching into realtime.
- In `realtime` mode, Gemini defaults still apply when fields are omitted: `provider="gemini"`, `model="gemini-3.1-flash-live-preview"`, `voice="Puck"`.
- In `realtime` mode, `assistant_llm_config.api_key` overrides the system `GOOGLE_API_KEY`.

## Switching Modes

=== ":material-pipe: Switch to Pipeline"

    When switching to `pipeline` mode, TTS fields are **only required if no TTS config is already stored on the assistant** (e.g. this assistant was created in pipeline mode before being switched to realtime — the original TTS config is preserved in the DB and reused automatically).

    If the assistant has never had a TTS config (e.g. it was originally created in realtime mode), you must provide both TTS fields in the same request.

    **Fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_llm_mode` | string | Yes | Set to `pipeline`. |
    | `assistant_tts_model` | string | Conditional | Required only if no TTS config exists in DB. |
    | `assistant_tts_config` | object | Conditional | Required if `assistant_tts_model` is provided. Must be sent together. |

    !!! note "Stale realtime LLM config is cleared automatically"
        When switching back to pipeline mode, any Gemini/realtime `assistant_llm_config` stored from the previous realtime session is automatically cleared. The assistant will fall back to the system `OPENAI_API_KEY` unless you explicitly provide a new `assistant_llm_config.api_key`.

    **Example — switching back when TTS already exists in DB**

    ```bash
    curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_llm_mode": "pipeline"
      }'
    ```

    **Example — switching when no TTS exists in DB**

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
    | `assistant_llm_config` | object | Yes | Realtime provider config. The object is required, but `provider`, `model`, and `voice` may be omitted to use defaults. |

    **Example request**

    ```bash
    curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_llm_mode": "realtime",
        "assistant_llm_config": {}
      }'
    ```

---

## Validation Rules

- TTS fields must come in pairs: send both `assistant_tts_model` and `assistant_tts_config`, or neither.
- In `pipeline` mode, `assistant_llm_config` may be omitted entirely.
- In `pipeline` mode, only `assistant_llm_config.api_key` affects runtime behavior.
- Switching to `realtime` requires `assistant_llm_config`.
- Switching to `pipeline` requires TTS fields **only if no TTS config exists in DB**. If the assistant previously had a TTS config, it is preserved and reused — you do not need to re-send it.
- When switching to `pipeline`, any stored realtime `assistant_llm_config` (e.g. Gemini keys) is automatically cleared unless you explicitly provide a new one.

## Runtime Behavior Notes

- `assistant_interaction_config.speaks_first` is supported in both `pipeline` and `realtime` modes.
- When `speaks_first=true`, `assistant_start_instruction` is used as the opening response.
- `assistant_interaction_config.background_sound_enabled` controls background ambience for all sessions using the assistant.
- `assistant_interaction_config.thinking_sound_enabled` controls the typing-style thinking sound for all sessions using the assistant.
- `assistant_interaction_config.allow_interruptions` controls whether users can interrupt the assistant's initial greeting. Default: `false`.
- `assistant_interaction_config.preferred_languages` accepts a list of BCP-47 codes (e.g. `["hi-IN", "en-US"]`). Pass an empty list `[]` to clear the hint and revert to auto-detection.
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
