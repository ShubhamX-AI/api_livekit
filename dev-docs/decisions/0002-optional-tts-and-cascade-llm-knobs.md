# 0002. Add TTS and cascade LLM knobs as optional keys that keep the old behaviour when absent

- **Status:** Accepted
- **Date:** 2026-08

## Context

Users wanted to tune speech (speed, pace, voice settings) and the cascade LLM (temperature,
reasoning effort, output limits). Existing assistants were already stored without any of these
keys, and they had to keep sounding and behaving exactly as before.

Two traps were known up front:

- Some LLM knobs are only accepted by some models, and OpenAI answers a wrong pairing with a 400
  on every turn (see [0001](0001-ask-openai-before-storing-a-config.md)).
- The ElevenLabs client treats `None` as "set", which crashes synthesis.

## Decision

New optional keys in `assistant_tts_config` and `assistant_llm_config`. **Omitting a key keeps
the old behaviour / the SDK default.** Anyone touching these must keep behaviour identical when
the key is absent.

### TTS providers (`assistant_tts_config`)

Factory: `src/core/agents/tts/factory.py`.

- **Cartesia**
  - `speed`: float `0`–`3`, default `1.0`. Preset strings are rejected: `sonic-3` needs a float.
  - `volume`: default `1.0`.
  - `emotion`: Sonic 3 only.
  - `language`: default `en`.
  - `pronunciation_dict_id`.
- **Sarvam**
  - `pace`: default `1.0`.
  - `speech_sample_rate`: default `24000`.
  - `temperature`: default `0.3`.
  - `target_language_code`.
  - These defaults match the SDK. Do not change them.
- **ElevenLabs**
  - `model`: default `eleven_v3`.
  - `voice_settings`: subkeys `stability`, `similarity_boost`, `style`, `speed`,
    `use_speaker_boost`.
  - **Critical:** when `voice_settings` is absent the factory passes `NOT_GIVEN`, never `None`.
    The client treats `None` as "set", and `dataclasses.asdict(None)` crashes on synthesis.
    Regression tests are in `tests/test_cascade_config.py`.

### Cascade LLM (`assistant_llm_config`, mode `cascade`, built as `openai.responses.LLM`)

- `model` **must** be in `OPENAI_CASCADE_MODELS`, otherwise `422`. Default `gpt-4.1`. The model
  is then also checked against OpenAI's own model list ([0001](0001-ask-openai-before-storing-a-config.md)).
- `temperature` (0–2): **ignored by reasoning models** (`gpt-5` / `gpt-5.x`), which take
  `reasoning_effort` instead. Examples must not show both on a reasoning model.
- `reasoning_effort`: `none|minimal|low|medium|high|xhigh|max`, reasoning models only. Which of
  those *values* a given model takes is per model, and is checked against OpenAI at
  create/update rather than guessed here.
- `max_output_tokens`, `service_tier`, `verbosity`, `tool_choice`, `parallel_tool_calls`:
  forwarded when set; omitted keeps the SDK default.
- The factory only forwards a knob when its config value is **non-None** (or truthy, for
  strings and bools).

## Consequences

- `docs/reference/models.md` keeps its "what changes if you change it" column per knob. Users
  rely on it; keep that style when adding a knob.
- Where the code has moved on since this decision:
  - `OPENAI_CASCADE_MODELS` is defined in `src/api/models/api_schemas/config/llm_config.py` as
    an alias of `CASCADE_MODELS` from `src/core/model_support/capabilities.py`.
  - `SarvamTTSConfig.temperature` now defaults to `None` in the schema, and the factory falls
    back to `0.3`, so the effective default is unchanged. `None` is stored instead of `0.3`
    because `bulbul:v4-flash` refuses the field ([0006](0006-duplex-mode-gpt-6-and-new-speech-models.md)).
  - `SarvamTTSConfig.target_language_code` defaults to `None`, see
    [0004](0004-one-rule-table-for-every-mode.md).
- Public reference for every knob: [create](../../docs/api/assistant/create.md),
  [update](../../docs/api/assistant/update.md), [models](../../docs/reference/models.md).

## Where in the code

| What | File | Symbol |
|---|---|---|
| TTS knob forwarding, `NOT_GIVEN` | `src/core/agents/tts/factory.py` | `create_tts` |
| TTS schemas | `src/api/models/api_schemas/config/tts_config.py` | `CartesiaTTSConfig`, `SarvamTTSConfig`, `ElevenLabsTTSConfig`, `ElevenLabsVoiceSettings` |
| Cascade LLM knob forwarding | `src/core/agents/llm/factory.py` | `create_llm` |
| Cascade LLM schema + allowlist | `src/api/models/api_schemas/config/llm_config.py` | `AssistantLLMConfig`, `OPENAI_CASCADE_MODELS` |
| Which model takes which knob | `src/core/model_support/capabilities.py` | `unsupported_knob_reason` |
