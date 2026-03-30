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
| `assistant_start_instruction` | string | No | First spoken instruction at call start (max 200 chars). |
| `assistant_interaction_config` | object | No | Interaction settings (see below). |
| `assistant_end_call_enabled` | boolean | No | Enables built-in end-call tool. Default: `false`. |
| `assistant_end_call_trigger_phrase` | string | Conditional | Required if `assistant_end_call_enabled=true`. |
| `assistant_end_call_agent_message` | string | Conditional | Required if `assistant_end_call_enabled=true`. |
| `assistant_end_call_url` | string | No | Webhook URL for call-ended payload. |

---

## Mode Configuration

=== ":material-pipe: Pipeline"

    **Pipeline mode** uses OpenAI Realtime for STT + LLM, with a separate TTS provider for audio output.

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_tts_model` | string | Yes | One of `cartesia`, `sarvam`, `elevenlabs`, `mistral`. |
    | `assistant_tts_config` | object | Yes | TTS config for the selected provider (see tabs below). |

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
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
        },
        "assistant_interaction_config": {
          "speaks_first": true,
          "filler_words": true,
          "silence_reprompts": true,
          "silence_reprompt_interval": 10.0,
          "silence_max_reprompts": 2
        }
      }'
    ```

=== ":material-lightning-bolt: Realtime"

    **Realtime mode** uses a single model (e.g. Gemini Live API) that handles STT, LLM, and TTS in one stream.

    !!! note "Filler words are not available in realtime mode"
        Since there is no external TTS, `filler_words` is automatically disabled even if set to `true`.

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_llm_config` | object | Yes | Realtime provider configuration (see table below). |

    **Realtime LLM config** (`assistant_llm_config`)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `provider` | string | No | Realtime provider. Current value: `gemini`. |
    | `model` | string | No | Gemini realtime model. Default: `gemini-2.5-flash`. |
    | `voice` | string | No | Gemini voice. Default: `Puck`. |
    | `api_key` | string | No | Optional per-assistant Google key. Falls back to system `GOOGLE_API_KEY`. |

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
          "model": "gemini-2.5-flash",
          "voice": "Puck"
        }
      }'
    ```

---

## Interaction Configuration

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `speaks_first` | boolean | No | If `true` (default), assistant starts first. |
| `filler_words` | boolean | No | Enables filler words while user is speaking. Pipeline mode only. |
| `silence_reprompts` | boolean | No | Enables reprompts during prolonged user silence. |
| `silence_reprompt_interval` | number | No | Reprompt interval in seconds (1.0-60.0). Default: `10.0`. |
| `silence_max_reprompts` | number | No | Maximum reprompts before ending session (0-5). Default: `2`. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Human-readable message. |
| `data.assistant_id` | string | Created assistant UUID. |
| `data.assistant_name` | string | Created assistant name. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Assistant created successfully. |
| 400 | Validation or payload mismatch error. |
| 401 | Unauthorized. |
| 500 | Internal server error. |
