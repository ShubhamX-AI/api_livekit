# 0004. Reject impossible mode combinations at the API with one rule table

- **Status:** Accepted
- **Date:** 2026-08

## Context

Many combinations of mode, LLM provider, model, STT and TTS were accepted by the API and then
failed at call time: the job died during startup, or the call connected and stayed silent. The
rules lived in several places, and a PATCH that changed only one field was judged without the
fields already stored on the assistant.

## Decision

Reject these combinations at the API. **If you add a provider or a mode, extend the same rule
table. Do not add a second one.**

- **`validate_mode_config(mode, llm_config, stt_model)`** in
  `src/api/models/api_schemas/config/llm_config.py` is the single rule table for all modes. It is
  called by both the `CreateAssistant` and `UpdateAssistant` validators. It covered three modes
  when this was decided; it now covers four, `duplex` included ([0006](0006-duplex-mode-gpt-6-and-new-speech-models.md)).
- **`enforce_stored_mode_constraints`** re-runs that same table against `stored row + PATCH`, so a
  mode switch cannot land a combination the request alone looked fine for. It answers `400`, not
  `422`: the request is well-formed, the merge is not. *Path moved:* it was in
  `src/api/routes/assistant.py` and now lives in `src/api/validation/assistant_guard.py`; the
  route imports it.
- **Gemini is rejected in `pipeline` and `cascade`.** Google's Live API cannot run the text-only
  modality that half-cascade needs on native-audio models (googleapis/python-genai#1780). The
  pipeline Gemini branch in `src/core/agents/session.py` is gone. Realtime Gemini is untouched and
  fully supported.
- **Three model allowlists**, all in `src/core/model_support/capabilities.py`, which do not
  overlap:
  - `REALTIME_MODELS`: pipeline + realtime, OpenAI.
  - `GEMINI_LIVE_MODELS`: realtime, Gemini. Gemini ids are no longer free-form: only five Live
    models existed, and a chat id fails at connect with nothing naming the cause.
  - `OPENAI_CASCADE_MODELS`: cascade (an alias of `CASCADE_MODELS`, re-exported from
    `llm_config.py`).
- **`extra="forbid"` is on every provider config**: all five STT shapes and all four TTS shapes,
  not just some. A typo is a `422`. (`NativeSTTConfig` has it too.)
- **Missing API keys are checked before the plugin is constructed** in *both* factories.
  `create_tts` returns `None`, as `create_stt` already did, instead of letting a plugin
  constructor raise out of `entrypoint()`.
- **`CartesiaTTSConfig.speed` is float-only.** The preset strings (`slow`/`normal`/`fast`) were
  accepted by the schema, but `sonic-3`, the pinned model, raises
  `ValueError: speed must be a float for sonic-3` inside the plugin constructor.
- **Deepgram is two plugin classes.** `nova-*` uses `deepgram.STT` (`/listen/v1`); `flux-*` uses
  `deepgram.STTv2` (`/listen/v2`, `language_hint` instead of `language`). Neither validates the
  model at construction, so `create_stt` dispatches on the name.
- **OpenAI STT streams only if you ask.** The plugin's `use_realtime` defaults to `False` (batch
  REST, no interim results); `create_stt` passes `True` because a live call needs streaming.
  `gpt-realtime-whisper` is rejected outright: it has no server-side endpointing, and the plugin
  then requires a `livekit-plugins-silero` VAD, which is not installed. The session's VAD is
  `inference.VAD`, which an STT plugin cannot take.
- **`assistant_stt_model="openai"` means two different things per mode.** Cascade builds the real
  OpenAI STT plugin. Pipeline collapses it to `native` (same vendor, same model, one less
  connection), which also keeps pre-migration rows working.
- **Sarvam TTS numeric bounds mirror the provider**, verified against the LiveKit Sarvam TTS
  page: `pace` 0.3–3.0, `temperature` 0.01–2.0 (not 0.0), `speech_sample_rate` an enum of
  8000/16000/22050/24000/32000/44100/48000 rather than a range.
- **`SarvamTTSConfig.target_language_code` defaults to `None`**, not `bn-IN`. The field is always
  serialized, so a concrete default silently overrode the factory's `en-IN` fallback for every
  assistant that omitted it.

## Consequences

- Do not re-add Cartesia speed presets without also un-pinning the `sonic-3` model.
- Adding a Deepgram model means first checking which family (`nova` or `flux`) it belongs to.
- Do not reintroduce a Gemini branch in pipeline or cascade.
- Do not give `target_language_code` a concrete default.
- Where the code has moved on since this decision:
  - OpenAI STT `use_realtime` is now a config field (`OpenAISTTConfig.use_realtime`, default
    `True`). `create_stt` forces it back to `True` for a token-billed model, because the batch
    path reports no tokens and the call would price as zero; only `whisper-1`
    (`OPENAI_STT_DURATION_BILLED_MODELS`) may take the batch path.
  - `gpt-realtime-whisper` is kept out of `OPENAI_STT_MODELS`, and `create_stt` repeats the
    refusal for rows written before that list existed.
- Legal combinations, for users: [compatibility](../../docs/reference/compatibility.md).

## Where in the code

| What | File | Symbol |
|---|---|---|
| The rule table | `src/api/models/api_schemas/config/llm_config.py` | `validate_mode_config` |
| Stored row + PATCH | `src/api/validation/assistant_guard.py` | `enforce_stored_mode_constraints` |
| Model allowlists | `src/core/model_support/capabilities.py` | `REALTIME_MODELS`, `GEMINI_LIVE_MODELS`, `CASCADE_MODELS` |
| Provider config shapes | `src/api/models/api_schemas/config/{stt,tts}_config.py` | `STTConfig`, `TTSConfig` unions |
| Deepgram / OpenAI STT dispatch | `src/core/agents/stt/factory.py` | `create_stt` |
| Pipeline STT resolution | `src/core/agents/stt/factory.py` | `resolve_stt` |
| Keyless TTS returns `None` | `src/core/agents/tts/factory.py` | `create_tts` |
