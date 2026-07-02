# Create Assistant

Create a new assistant configuration.

- **URL**: `/assistant/create`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

## Request Body (Common Fields)

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_name` | string | Yes | Assistant name (1-100 chars). |
| `assistant_description` | string | Yes | Assistant description. |
| `assistant_prompt` | string | Yes | System prompt. |
| `assistant_llm_mode` | string | No | LLM mode: `pipeline` or `realtime`. Default: `pipeline`. |
| `assistant_start_instruction` | string | No | Opening response text. Used when `assistant_interaction_config.speaks_first=true` (max 200 chars). |
| `assistant_interaction_config` | object | No | Interaction settings (see below). |
| `assistant_greeting_audio` | object | No | Prerecorded greeting reference: `{ "enabled": bool, "audio_id": string }`. `audio_id` must reference one of your active [audio assets](../../api/audio/index.md). When `enabled` and `speaks_first=true`, the clip plays instead of a model-generated greeting. |
| `assistant_end_call_enabled` | boolean | No | Enables built-in end-call tool. Default: `false`. |
| `assistant_end_call_trigger_phrase` | string | Conditional | Required if `assistant_end_call_enabled=true`. |
| `assistant_end_call_agent_message` | string | Conditional | Required if `assistant_end_call_enabled=true`. |
| `assistant_end_call_url` | string | No | Webhook URL for call-ended payload. |

---

## Mode Configuration

=== ":material-pipe: Pipeline"

    **Pipeline mode** (half-cascade): the LLM emits text and a separate TTS provider speaks it.
    The LLM vendor is set by `assistant_llm_config.provider` — `openai` (default) or `gemini`; both emit text into the external TTS.
    If `assistant_interaction_config.speaks_first=true`, the opening response is spoken at session start.
    `assistant_llm_config` is optional in this mode (defaults to `openai`). Send it to pick `gemini`, override the model, or set an `api_key`; `voice` is ignored (TTS handles audio).

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_tts_model` | string | Yes | One of `cartesia`, `sarvam`, `elevenlabs`, `mistral`. |
    | `assistant_tts_config` | object | Yes | TTS config for the selected provider (see tabs below). |

    **Optional pipeline LLM config** (`assistant_llm_config`)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `api_key` | string | No | Optional per-assistant OpenAI key. Overrides system `OPENAI_API_KEY`. |

    **TTS provider configuration**

    === "Cartesia"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | Cartesia voice ID. |
        | `api_key` | string | No | Optional Cartesia API key. |

    === "Sarvam"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `speaker` | string | Yes | Sarvam speaker identifier. |
        | `target_language_code` | string | No | BCP-47 code. Default: `bn-IN`. |
        | `api_key` | string | No | Optional Sarvam API key. |

    === "ElevenLabs"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | ElevenLabs voice ID. |
        | `api_key` | string | No | Optional ElevenLabs API key. |

    === "Mistral"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | Mistral voice ID. |
        | `api_key` | string | No | Optional Mistral API key. |

    **Example request**

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Support Bot",
        "assistant_description": "First line support",
        "assistant_prompt": "You are a helpful customer support agent.",
        "assistant_llm_mode": "pipeline",
        "assistant_llm_config": {
          "api_key": "sk-..."
        },
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
        },
        "assistant_interaction_config": {
          "speaks_first": true,
          "filler_words": true,
          "silence_reprompts": true,
          "silence_reprompt_interval": 10.0,
          "silence_max_reprompts": 2,
          "background_sound_enabled": true,
          "thinking_sound_enabled": true,
          "preferred_languages": ["en-US", "hi-IN"],
          "max_call_duration_minutes": 30
        }
      }'
    ```

=== ":material-lightning-bolt: Realtime"

    **Realtime mode** uses a single model (e.g. Gemini Live API) that handles STT, LLM, and TTS in one stream.
    If `assistant_interaction_config.speaks_first=true`, the opening response is sent at session start through the realtime conversation path.
    `assistant_llm_config` is required in this mode, but its Gemini fields still have defaults.

    !!! note "Filler words are not available in realtime mode"
        Since there is no external TTS, `filler_words` is automatically disabled even if set to `true`.

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_llm_config` | object | Yes | Realtime provider configuration (see table below). |

    **Realtime LLM config** (`assistant_llm_config`)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `provider` | string | No | LLM vendor for audio-out realtime. `gemini` (default) or `openai`. |
    | `model` | string | No | Provider model. Gemini default: `gemini-3.1-flash-live-preview`; OpenAI default: `gpt-realtime-1.5`. |
    | `voice` | string | No | Voice for the audio-out model. Gemini default: `Puck`; OpenAI default: `marin`. |
    | `api_key` | string | No | Optional per-assistant provider key. Falls back to system `GOOGLE_API_KEY` / `OPENAI_API_KEY`. |

    !!! tip "Sarvam parallel STT (pipeline mode)"
        In `pipeline` mode (either provider), user transcripts default to Sarvam Saras v3 (see `assistant_interaction_config.user_stt_provider` below) — native-script Indic transcripts for code-switched calls. The LLM still consumes the audio directly for understanding. Realtime (audio-out) mode transcribes via the model itself.

    **Minimal realtime example**

    ```json
    {
      "assistant_llm_mode": "realtime",
      "assistant_llm_config": {}
    }
    ```

    **Example request**

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Gemini Assistant",
        "assistant_description": "Realtime voice assistant",
        "assistant_prompt": "You are a helpful assistant.",
        "assistant_llm_mode": "realtime",
        "assistant_llm_config": {
          "provider": "gemini",
          "model": "gemini-3.1-flash-live-preview",
          "voice": "Puck"
        }
      }'
    ```

---

## Interaction Configuration

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `speaks_first` | boolean | No | If `true` (default), assistant sends an opening response first in both `pipeline` and `realtime` modes. |
| `filler_words` | boolean | No | Enables filler words while user is speaking. Pipeline mode only. |
| `silence_reprompts` | boolean | No | Enables reprompts during prolonged user silence. |
| `silence_reprompt_interval` | number | No | Reprompt interval in seconds (1.0-60.0). Default: `10.0`. |
| `silence_max_reprompts` | number | No | Maximum reprompts before ending session (0-5). Default: `2`. |
| `background_sound_enabled` | boolean | No | Enables background ambience. Default: `true`. |
| `thinking_sound_enabled` | boolean | No | Enables the typing-style thinking sound. Default: `true`. |
| `allow_interruptions` | boolean | No | If `true`, users can interrupt the assistant's initial greeting. Default: `false` (greeting is uninterruptible). |
| `preferred_languages` | array of strings | No | BCP-47 language codes the agent supports (e.g. `["hi-IN", "en-US", "ta-IN"]`). Used to hint the STT model when the speaker is multilingual or switches between languages. If omitted, the STT model auto-detects all languages. |
| `user_stt_provider` | string | No | User-transcription source in `pipeline` mode (either provider). `sarvam` (default) runs Sarvam Saras v3 as a parallel audio tap — native-script Indic transcripts, avoids script-switching hallucinations. `native` lets the conversational LLM transcribe itself (OpenAI `gpt-4o-transcribe`, or Gemini's own on a Gemini pipeline). Ignored in `realtime` (audio-out) mode, where the model transcribes. |
| `max_call_duration_minutes` | number | No | Hard ceiling on active-call length in minutes (must be `> 0`). When the limit is reached, the assistant speaks a brief farewell and the call is torn down gracefully (recording, transcripts, usage and webhook all finalize cleanly). When unset or `null`, the platform default of **30 minutes** applies. Does not apply to passthrough calls (no AI agent). The call termination reason is reported as `max_duration_exceeded` in the end-of-call webhook payload and in the `CallRecord.call_end_reason` field. |

These sound settings are assistant defaults and apply to runtime sessions started through the call and web-call APIs. Those APIs do not expose per-call sound overrides.

!!! note "Text-only web calls override these flags"
    When `POST /web_call/get_token` is called with `"text_only": true`, the session has no audio I/O. Filler words, silence reprompts, background sound, thinking sound, and the per-utterance input guard are all force-disabled for that session regardless of the assistant's saved values — they require an audio channel that does not exist in text mode. The stored assistant config is not modified; voice web calls and phone calls for the same assistant still honor it.

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Human-readable message. |
| `data.assistant_id` | string | Created assistant UUID. |
| `data.assistant_name` | string | Created assistant name. |

## Example Response

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

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Assistant created successfully. |
| 400 | Validation or payload mismatch error. |
| 401 | Unauthorized. |
| 500 | Internal server error. |
