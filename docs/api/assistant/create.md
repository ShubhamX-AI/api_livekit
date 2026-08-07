# Create Assistant

Create a new assistant configuration.

For the full model/provider inventory (model IDs, defaults, per-mode validity) see
[Models & Providers](../../reference/models.md).

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
| `assistant_mode` | string | No | Runtime mode: `pipeline`, `realtime` or `cascade`. Default: `pipeline`. |
| `assistant_start_instruction` | string | No | Opening response text. Used when `assistant_interaction_config.speaks_first=true` (max 500 chars). |
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
    The LLM vendor is `openai` only — `assistant_llm_config.provider: "gemini"` returns `422` here, because Google's Live API cannot run the text-only modality half-cascade needs on its native-audio models. Use `assistant_mode: "realtime"` for Gemini. See the [Compatibility Matrix](../../reference/compatibility.md#mode-llm-provider).
    If `assistant_interaction_config.speaks_first=true`, the opening response is spoken at session start.
    `assistant_llm_config` is optional in this mode (defaults to `provider="openai"`, `model="gpt-realtime-1.5"`). Send it to override the model — it must be an OpenAI **realtime** model ID — or to set an `api_key`; `voice` is ignored (TTS handles audio).

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_tts_model` | string | Yes | One of `cartesia`, `sarvam`, `elevenlabs`, `mistral`. |
    | `assistant_tts_config` | object | Yes | TTS config for the selected provider (see tabs below). |

    **Optional pipeline LLM config** (`assistant_llm_config`)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `api_key` | string | No | Optional per-assistant OpenAI key. Overrides system `OPENAI_API_KEY`. |

    **STT configuration** (optional — defaults to Sarvam with the system key)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_stt_model` | string | No | User-transcription source: `sarvam` (default when unset) or `native`. `cartesia`, `deepgram` and `elevenlabs` are cascade-only. |
    | `assistant_stt_config` | object | No | Config for the selected STT provider (see tabs below). Requires `assistant_stt_model`. Omit for provider defaults. |

    === "Sarvam"

        Runs Sarvam Saras v3 as a parallel audio tap — native-script Indic transcripts, avoids the script-switching hallucinations of a generic model on code-switched speech. The LLM still consumes the audio directly for understanding.

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `model` | string | No | Sarvam STT model. Default: `saaras:v3`. |
        | `language` | string | No | BCP-47 code, or `unknown` to auto-detect. Default: `unknown`. |
        | `mode` | string | No | Transcription mode. Default: `codemix` (keeps code-switching intact). `saaras:v3` only. |
        | `api_key` | string | No | Optional Sarvam API key. Falls back to system `SARVAM_API_KEY`. **Distinct from `assistant_tts_config.api_key`**, which belongs to whichever TTS provider you selected — Sarvam STT rejects a Cartesia/ElevenLabs/Mistral key with `403`. Masked in `GET /assistant/details` and `GET /assistant/list`. |

        Allowed `model` and `mode` values: [Models & Providers](../../reference/models.md#stt).

    === "Native"

        The conversational LLM transcribes itself (OpenAI `gpt-4o-mini-transcribe`, or Gemini's own on a Gemini pipeline). No configuration fields — send `{}` or omit `assistant_stt_config`.

        Not valid in `cascade` mode — there is no realtime model to transcribe itself.

    Ignored in `realtime` (audio-out) mode, where the model always transcribes.

    **TTS provider configuration**

    === "Cartesia"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | Cartesia voice ID. |
        | `language` | string | No | BCP-47 code for the input text. Default: `en`. Affects pronunciation only. |
        | `speed` | number | No | Speaking speed as a numeric multiplier of normal (e.g. `1.5` = 50% faster), range `0`–`3`. Default: `1.0`. Preset strings (`slow`/`normal`/`fast`) are **not** accepted: they belong to Cartesia's older models, and `sonic-3` requires a float. |
        | `volume` | number | No | Output volume where `1.0` is the default. Range `0`–`3`. |
        | `emotion` | string | No | Emotion control string (Sonic 3 only), e.g. `excited`, `calm`, `sad`. See [Cartesia docs](https://docs.cartesia.ai/build-with-cartesia/sonic-3/volume-speed-emotion) for supported values. |
        | `pronunciation_dict_id` | string | No | ID of a Cartesia pronunciation dictionary to apply (Sonic 3 models only). |
        | `api_key` | string | No | Optional Cartesia API key. Falls back to system `CARTESIA_API_KEY`. |

    === "Sarvam"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `speaker` | string | Yes | Sarvam speaker identifier. |
        | `target_language_code` | string | No | BCP-47 code. Default: `bn-IN`. |
        | `pace` | number | No | Speaking pace multiplier, `0.3`–`3.0`. Default: `1.0` (`>1.0` faster, `<1.0` slower). |
        | `speech_sample_rate` | number | No | Output sample rate in Hz. One of `8000`, `16000`, `22050`, `24000`, `32000`, `44100`, `48000` — other values are rejected. Default: `24000`; use `8000` only for narrowband telephony. |
        | `temperature` | number | No | TTS sampling temperature, `0.01`–`2.0`. Default: `0.3`. Lower = more stable. |
        | `api_key` | string | No | Optional Sarvam API key. Falls back to system `SARVAM_API_KEY`. |

    === "ElevenLabs"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | ElevenLabs voice ID. |
        | `model` | string | No | TTS model. Default: `eleven_v3`. Also `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`. |
        | `voice_settings` | object | No | Voice tuning: `{ "stability": 0–1, "similarity_boost": 0–1, "style": 0–1, "speed": 0.25–4.0, "use_speaker_boost": bool }`. |
        | `api_key` | string | No | Optional ElevenLabs API key. Falls back to system `ELEVENLABS_API_KEY`. |

    === "Mistral"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `voice_id` | string | Yes | Mistral voice ID. |
        | `api_key` | string | No | Optional Mistral API key. Falls back to system `MISTRAL_API_KEY`. |

    **Example request**

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Support Bot",
        "assistant_description": "First line support",
        "assistant_prompt": "You are a helpful customer support agent.",
        "assistant_mode": "pipeline",
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
        In `pipeline` mode (either provider), user transcripts default to Sarvam Saras v3 (see `assistant_stt_model` in the Pipeline tab) — native-script Indic transcripts for code-switched calls. The LLM still consumes the audio directly for understanding. Realtime (audio-out) mode transcribes via the model itself.

    **Minimal realtime example**

    ```json
    {
      "assistant_mode": "realtime",
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
        "assistant_mode": "realtime",
        "assistant_llm_config": {
          "provider": "gemini",
          "model": "gemini-3.1-flash-live-preview",
          "voice": "Puck"
        }
      }'
    ```

=== "Cascade Mode"

    A true three-stage pipeline: plugin STT → plain OpenAI chat model → plugin TTS. Each stage is
    separately metered, so this is the only mode that reports STT cost on its own. Full detail in
    [Cascade Pipeline](../../architecture/cascade-pipeline.md).

    **Required fields**

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_tts_model` | string | Yes | One of `cartesia`, `sarvam`, `elevenlabs`, `mistral`. |
    | `assistant_tts_config` | object | Yes | TTS config for the selected provider (same tabs as the Pipeline tab). |

    **STT stage** (optional — defaults to Sarvam with the system key)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `assistant_stt_model` | string | No | `sarvam` (default when unset), `cartesia`, `deepgram` or `elevenlabs`. **`native` is rejected** — there is no realtime model to transcribe itself. |
    | `assistant_stt_config` | object | No | Config for the selected STT provider — `sarvam`, `cartesia`, `deepgram` or `elevenlabs` (see tabs below). Requires `assistant_stt_model`. Omit for provider defaults. |

    === "Sarvam (multilingual)"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `model` | string | No | Sarvam STT model. Default: `saaras:v3`. |
        | `language` | string | No | `unknown` (default) auto-detects; or a fixed BCP-47 code. |
        | `mode` | string | No | Transcription mode. Default: `codemix`. |
        | `api_key` | string | No | Falls back to system `SARVAM_API_KEY`. |

        The default `saaras:v3` + `unknown` + `codemix` combination is the multilingual one: it
        auto-detects the language and keeps code-switching intact inside a single utterance.

    === "Cartesia (single language)"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `model` | string | No | Cartesia STT model. Default: `ink-whisper` (multilingual). |
        | `language` | string | No | Fixed BCP-47 code. Default: `en`. **No auto-detect** — use Sarvam if the caller may switch languages. |
        | `api_key` | string | No | Falls back to system `CARTESIA_API_KEY`. |

        Allowed `model`, `language` and `mode` values for the Sarvam and Cartesia tabs: [Models & Providers](../../reference/models.md#stt).

    === "Deepgram (multilingual)"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `model` | string | No | Deepgram STT model. Default: `nova-3` (multilingual, 45 languages). Also `nova-2`, `flux-general-en` (English only) and `flux-general-multi` (multilingual). |
        | `language` | string | No | BCP-47 code, or `multi` to auto-detect. When omitted, falls back to the first entry of `assistant_interaction_config.preferred_languages`, then `en`. `multi` auto-detects per segment; pin a fixed BCP-47 code to force one language (a caller switching languages is then mis-transcribed). |
        | `enable_diarization` | boolean | No | Labels each utterance with a speaker id. Default: `false`. When omitted, diarization stays off — it is never force-enabled. Nova models only. |
        | `keyterm` | string or array of strings | No | Boosts recognition of a term. When omitted it is not sent (no biasing). `nova-3` / `flux` only — `nova-2` does not take keyterm. |
        | `api_key` | string | No | Optional Deepgram API key. Falls back to system `DEEPGRAM_API_KEY`. |

    === "ElevenLabs (auto-detect)"

        | Field | Type | Required | Description |
        | :--- | :--- | :--- | :--- |
        | `model` | string | No | ElevenLabs STT model. Default: `scribe_v2_realtime` (auto-detects ~190 languages). Also `scribe_v2` and `scribe_v1`. |
        | `language_code` | string | No | BCP-47 code. When omitted, the factory falls back to the first entry of `assistant_interaction_config.preferred_languages`, else the provider auto-detects. When set, auto-detection is disabled and the code is pinned. |
        | `no_verbatim` | boolean | No | Strips filler words (`um`, `uh`) and false starts from the transcript. Default: `false`. |
        | `api_key` | string | No | Optional ElevenLabs key for the STT stage. Falls back to system `ELEVENLABS_API_KEY`, the same variable the ElevenLabs TTS provider uses. |

    > **Don't assume all STT providers auto-detect when `language`/`language_code` is omitted.**
    > ElevenLabs auto-detects, but Deepgram falls back to `en` (not `multi`), and `flux-general-en` is
    > English-only. `keyterm` is ignored on `nova-2`, `enable_diarization` is nova-only, and a pinned
    > ElevenLabs `language_code` disables auto-detect. Full list:
    > [STT pitfalls & what not to combine](../../reference/models.md#stt-pitfalls-what-not-to-combine).

    **LLM stage** (`assistant_llm_config`)

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `provider` | string | No | Must be `openai` (the default when unset). Any other value is rejected. |
    | `model` | string | No | One of the documented OpenAI models. Default: `gpt-4.1`. Full list and knobs: [Models & Providers](../../reference/models.md#cascade-llm-cascade-mode-only). |
    | `api_key` | string | No | Falls back to system `OPENAI_API_KEY`. |
    | `temperature` | number | No | Sampling temperature `0`–`2`. Higher = more random. **Ignored by reasoning models** (`gpt-5.x`). |
    | `max_output_tokens` | integer | No | Cap on the number of output tokens in the response. |
    | `reasoning_effort` | string | No | Reasoning depth: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. **Reasoning models only** (`gpt-5`, `gpt-5.x`). |
    | `service_tier` | string | No | OpenAI processing/billing tier: `auto`, `default`, `flex`, `scale`, `priority`. |
    | `verbosity` | string | No | Constrains response length: `low`, `medium`, `high`. |
    | `tool_choice` | string | No | Tool usage: `auto`, `required`, `none`. |
    | `parallel_tool_calls` | boolean | No | Allow multiple tool calls in one response. |

    `voice` is ignored — the TTS provider owns the voice in this mode. Any unknown key in
    `assistant_llm_config` is rejected with `422`.

    **Example request** (with the new LLM generation knobs and TTS speed settings; all are optional)

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Cascade Assistant",
        "assistant_description": "True STT -> LLM -> TTS pipeline",
        "assistant_prompt": "You are a helpful assistant.",
        "assistant_mode": "cascade",
        "assistant_stt_model": "sarvam",
        "assistant_stt_config": {
          "model": "saaras:v3",
          "language": "unknown",
          "mode": "codemix"
        },
        "assistant_llm_config": {
          "provider": "openai",
          "model": "gpt-5-mini",
          "reasoning_effort": "low",
          "max_output_tokens": 500,
          "verbosity": "medium",
          "service_tier": "default",
          "tool_choice": "auto",
          "parallel_tool_calls": true
        },
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
          "speed": 1.1,
          "volume": 1.0,
          "emotion": "calm",
          "language": "en"
        }
      }'
    ```

    > **Note on the example above:** `gpt-5-mini` is a *reasoning* model, which ignores
    > `temperature` — so the example sends `reasoning_effort` instead. For a **non-reasoning**
    > model (like the default `gpt-4.1`), do the opposite: send `temperature` and drop
    > `reasoning_effort`. Both are optional — omit whichever your model family does not use.

    **Example request — Deepgram STT**

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Cascade Assistant",
        "assistant_description": "True STT -> LLM -> TTS pipeline",
        "assistant_prompt": "You are a helpful assistant.",
        "assistant_mode": "cascade",
        "assistant_stt_model": "deepgram",
        "assistant_stt_config": {
          "model": "nova-3",
          "language": "multi",
          "enable_diarization": true,
          "keyterm": "invoice",
          "api_key": "dg-..."
        },
        "assistant_llm_config": {
          "provider": "openai",
          "model": "gpt-5-mini",
          "max_output_tokens": 500,
          "reasoning_effort": "low",
          "verbosity": "medium",
          "service_tier": "default",
          "tool_choice": "auto",
          "parallel_tool_calls": true
        },
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
          "speed": 1.1,
          "volume": 1.0,
          "emotion": "calm",
          "language": "en"
        }
      }'
    ```

    **Example request — ElevenLabs STT**

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_api_key>" \
      -d '{
        "assistant_name": "Cascade Assistant",
        "assistant_description": "True STT -> LLM -> TTS pipeline",
        "assistant_prompt": "You are a helpful assistant.",
        "assistant_mode": "cascade",
        "assistant_stt_model": "elevenlabs",
        "assistant_stt_config": {
          "model": "scribe_v2_realtime",
          "no_verbatim": true,
          "api_key": "el-stt-..."
        },
        "assistant_llm_config": {
          "provider": "openai",
          "model": "gpt-5-mini",
          "max_output_tokens": 500,
          "reasoning_effort": "low",
          "verbosity": "medium",
          "service_tier": "default",
          "tool_choice": "auto",
          "parallel_tool_calls": true
        },
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
          "speed": 1.1,
          "volume": 1.0,
          "emotion": "calm",
          "language": "en"
        }
      }'
    ```

---

## Interaction Configuration

!!! warning "`user_stt_provider` and `stt_api_key` were moved"
    STT is now selected like TTS, through the top-level `assistant_stt_model` + `assistant_stt_config` pair (see the Pipeline tab above). Sending the old `assistant_interaction_config.user_stt_provider` or `.stt_api_key` keys now fails with `422` — silently ignoring them would have dropped per-assistant Sarvam keys. Existing assistants are migrated by `scripts/migrate_stt_config.py`; behavior is unchanged.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `speaks_first` | boolean | No | If `true` (default), assistant sends an opening response first in all three modes. |
| `filler_words` | boolean | No | Enables filler words while user is speaking. Requires an external TTS — available in `pipeline` and `cascade`, not `realtime`. |
| `silence_reprompts` | boolean | No | Enables reprompts during prolonged user silence. |
| `silence_reprompt_interval` | number | No | Reprompt interval in seconds (1.0-60.0). Default: `10.0`. |
| `silence_max_reprompts` | number | No | Maximum reprompts before ending session (0-5). Default: `2`. |
| `background_sound_enabled` | boolean | No | Enables background ambience. Default: `true`. |
| `thinking_sound_enabled` | boolean | No | Enables the typing-style thinking sound. Default: `true`. |
| `allow_interruptions` | boolean | No | If `true`, users can interrupt the assistant's initial greeting. Default: `false` (greeting is uninterruptible). |
| `input_guard_window_sec` | number | No | Seconds at the start of **every** agent reply during which caller audio is blanked (0.0-10.0). Default: `3.0`. Blocks repeated "Hello? Hello?" and short filler sounds ("um", "uh") from cutting the agent off — the noise gate cannot filter those, since they are genuine speech. Raise it to reject more fillers; the caller also cannot genuinely interrupt within the window. `0` disables the guard. Unmutes early if the reply finishes first. |
| `preferred_languages` | array of strings | No | BCP-47 language codes the agent supports (e.g. `["hi-IN", "en-US", "ta-IN"]`). Used to hint the STT model when the speaker is multilingual or switches between languages. If omitted, the STT model auto-detects all languages. |
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

## API Keys

Provider keys are stored as sent — they are not checked against the provider, so a wrong key first shows up as a failure during a call. Every `api_key` is returned masked by `GET /assistant/details` and `GET /assistant/list`, and sending a masked value back is rejected with `422`.
