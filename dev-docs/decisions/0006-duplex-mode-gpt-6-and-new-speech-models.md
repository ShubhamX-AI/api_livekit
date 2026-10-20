# 0006. Add duplex mode, GPT-6 and new speech models on livekit-agents 1.8.8 (release 1.6.0)

- **Status:** Accepted
- **Date:** 2026-10

## Context

`livekit-agents` 1.8.8 brought OpenAI GPT-Live, a model that listens while it speaks and decides
its own turns. It does not fit any existing mode: it is a `DuplexModel`, not a `RealtimeModel`,
and it hands reasoning and tools to a second "backend" model. The same release window brought
GPT-6 and new ElevenLabs and Sarvam models, and OpenAI announced the retirement of two models we
allowlisted.

The speech side also had a quiet problem: TTS settings that the chosen model ignores were
accepted. They did nothing, or, for a retired ElevenLabs model, failed every call.

## Decision

`livekit-agents` is pinned to `~=1.8.8` (was `~=1.8.2`), in `pyproject.toml` **and**
`docker/requirements-agent.txt`. `mistralai` is held below 3 to match the agent image.

- **New `duplex` mode**, built by `create_gpt_live` in `src/core/agents/llm/factory.py`.
  - A fourth branch in `validate_mode_config`: model `gpt-live-1`, a GPT-Live voice, and a
    reasoning `backend_model` that takes the tools and the generation knobs.
  - Greeting audio, filler words, `text_only` and `temperature` are refused.
  - Gates 3 and 4 (the two OpenAI checks from [0001](0001-ask-openai-before-storing-a-config.md))
    run against both models.
  - Switching into or out of duplex clears `assistant_llm_config`.
  - Architecture: [`docs/concepts/duplex.md`](../../docs/concepts/duplex.md) (behaviour), [`dev-docs/subsystems/agent-session.md`](../subsystems/agent-session.md) (build).
- **Models added**:
  - `gpt-6-luna`, `gpt-6-sol` (cascade + duplex backend);
  - `gpt-realtime-2.1`, `gpt-realtime-2.1-mini`;
  - ElevenLabs `eleven_v4` / `eleven_v4_turbo`;
  - Sarvam `bulbul:v4-flash`, through a new `assistant_tts_config.model` field, with its own
    224-speaker roster and the 12 IN22 languages.
- **Models removed**: `gpt-5.1` and `gpt-5.4-nano`. OpenAI retires both on 2027-04-01.
- **TTS settings a model ignores are a 422**:
  - ElevenLabs `voice_settings`, per model: `ELEVENLABS_UNREAD_SETTINGS` in
    `src/core/model_support/speech.py`, built from ElevenLabs' `/v1/models` flags and model notes.
  - Sarvam `temperature` on `bulbul:v4-flash`.
  - The retired `eleven_monolingual_v1` / `eleven_multilingual_v1` are rejected too.
- **Pricing**:
  - a `session_second` rate for GPT-Live;
  - a dated-snapshot fallback for reasoning models (a dated id such as `<alias>-YYYY-MM-DD` is
    priced as its alias);
  - current ElevenLabs rates.

  Every rate is listed on `docs/reference/pricing.md`, and a test fails when a rated model is
  missing there.

## Consequences

- Run the migrations after deploying:
  - `uv run python scripts/migrate_retired_models.py --apply` moves stored rows from `gpt-5.1` to
    `gpt-6-sol` and from `gpt-5.4-nano` to `gpt-6-luna` (both `model` and `backend_model`; a stored
    `reasoning_effort: "minimal"` becomes `"none"`, because GPT-6 refuses `minimal`).
  - `uv run python scripts/migrate_tts_settings.py --apply` cleans stored TTS rows. Until it runs,
    the factory drops the ignored settings at call time.
  - Both scripts dry-run without `--apply`.
- Until `migrate_retired_models.py` runs, a row still holding a removed model keeps running until
  2027-04-01, but every PATCH to it is refused.
- `gpt-5.1` and `gpt-5.4-nano` stay in `OPENAI_RATES` so calls made before the removal still price.
- Duplex has no TTS, so `session.say()` raises. That is why greeting audio, filler words and
  `text_only` are refused at the API rather than at call time.
- Adding a rated model means adding it to `docs/reference/pricing.md` in the same change, or
  `test_every_rated_model_is_on_the_pricing_page` fails.

## Where in the code

| What | File | Symbol |
|---|---|---|
| Duplex build | `src/core/agents/llm/factory.py` | `create_gpt_live` |
| Duplex rules | `src/api/models/api_schemas/config/llm_config.py` | `_validate_duplex`, `validate_mode_config` |
| GPT-Live model, voices, backend default | `src/core/model_support/capabilities.py` | `GPT_LIVE_MODELS`, `GPT_LIVE_VOICES`, `DEFAULT_DUPLEX_BACKEND_MODEL` |
| Clearing the LLM config on a duplex switch | `src/api/routes/assistant.py` | `update_assistant` |
| `text_only` refusal | `src/api/routes/web_call.py` | `get_token` |
| ElevenLabs unread settings | `src/core/model_support/speech.py` | `ELEVENLABS_UNREAD_SETTINGS`, `unread_elevenlabs_settings` |
| Sarvam v4 roster | `src/core/model_support/speech.py` | `SARVAM_SPEAKERS_BY_MODEL`, `SARVAM_TTS_MODELS` |
| Rates | `src/core/pricing/rates.py` | `OPENAI_REALTIME_RATES` (`gpt-live-1`), `_SNAPSHOT_PRICED_AS_ALIAS`, `ELEVENLABS_TTS_RATES` |
| Pricing-page test | `tests/test_provider_pricing.py` | `test_every_rated_model_is_on_the_pricing_page` |
