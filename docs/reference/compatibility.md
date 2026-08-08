# Compatibility Matrix

Which combinations of `assistant_mode`, LLM provider, STT provider and TTS provider actually run —
and what happens when you pick one that doesn't. [Models & Providers](models.md) documents *what each
knob does*; this page documents *what you are allowed to combine*.

Sourced from the validators in `src/api/models/api_schemas/config/llm_config.py` and
`src/api/routes/assistant.py`, and from the runtime in `src/core/agents/session.py` plus the three
factories under `src/core/agents/`. If this page and any other doc disagree, check the code — and
then fix whichever doc is wrong.

## Legend

| Symbol | Meaning |
|---|---|
| :white_check_mark: | Supported. Validated at create/update, works at call time. |
| :warning: | Accepted and stored, but the field has no effect in this mode. Not an error. |
| :recycle: | Accepted, then degraded at call time to something else, with a warning in the logs. |
| :no_entry: | Rejected by the API with `422` (create / mode-naming update) or `400` (update against stored state). |

---

## Mode × LLM provider

`assistant_llm_config.provider`.

| Provider | `pipeline` | `realtime` | `cascade` |
|---|---|---|---|
| `openai` | :white_check_mark: `gpt-realtime-1.5` in text-only modality, external TTS speaks | :white_check_mark: `gpt-realtime-1.5` speaks its own audio | :white_check_mark: `openai.responses.LLM` (a plain chat model) |
| `gemini` | :no_entry: rejected | :white_check_mark: `gemini-3.1-flash-live-preview`, handles STT+LLM+TTS | :no_entry: rejected |
| omitted | :white_check_mark: defaults to `openai` | :white_check_mark: defaults to `gemini` | :white_check_mark: defaults to `openai` |

!!! warning "Gemini is realtime-only"
    Gemini used to be selectable in `pipeline` mode and is now rejected at the API. Pipeline mode is
    a [half-cascade](https://docs.livekit.io/agents/models/pipelines.md#half-cascade): the realtime
    model must run in a **text-only response modality** so an external TTS can speak the result.
    Google's Live API only supports that on **non-native-audio** models
    ([googleapis/python-genai#1780](https://github.com/googleapis/python-genai/issues/1780)), and the
    Live models this platform targets are native-audio. The 3.1 Live line additionally ignores
    `generate_reply()`, `update_instructions()` and `update_chat_ctx()`, which the greeting and
    agent-handoff paths depend on.

    **Use Gemini with `assistant_mode: "realtime"`**, where it is fully supported, or use
    `provider: "openai"` in pipeline mode.

### Model IDs

`assistant_llm_config.model` is validated against a different list in each mode, because each mode
talks to a different API.

| Mode | Accepted models | On anything else |
|---|---|---|
| `pipeline` | `OPENAI_REALTIME_MODELS` — `gpt-realtime`, `gpt-realtime-1.5`, `gpt-realtime-mini`, `gpt-4o-realtime-preview`, `gpt-4o-mini-realtime-preview` | `422`. A chat model such as `gpt-4.1` belongs to cascade mode. |
| `realtime` + `openai` | same `OPENAI_REALTIME_MODELS` list | `422` |
| `realtime` + `gemini` | any string — deliberately unvalidated | accepted; a bad ID fails when the session connects |
| `cascade` | `OPENAI_CASCADE_MODELS` — the 22 chat models listed in [Models & Providers](models.md#cascade-llm-cascade-mode-only) | `422` |

Gemini Live model IDs are left free-form on purpose: Google ships new ones frequently and an
allowlist would reject them the day they land. Both OpenAI allowlists live in
`src/api/models/api_schemas/config/llm_config.py` — add new IDs there, and update this page.

---

## Mode × STT provider

`assistant_stt_model`. Unset means `sarvam`.

| Provider | `pipeline` | `realtime` | `cascade` |
|---|---|---|---|
| `sarvam` (default) | :white_check_mark: parallel Saras v3 audio tap alongside the realtime model | :warning: ignored — the realtime model transcribes | :white_check_mark: the session's own STT stage |
| `native` | :white_check_mark: the conversational LLM transcribes itself | :warning: ignored (this is effectively what realtime does anyway) | :no_entry: rejected — there is no realtime model to self-transcribe |
| `cartesia` | :recycle: degrades to `native` with a warning | :warning: ignored | :white_check_mark: |
| `deepgram` | :recycle: degrades to `native` with a warning | :warning: ignored | :white_check_mark: |
| `elevenlabs` | :recycle: degrades to `native` with a warning | :warning: ignored | :white_check_mark: |
| `openai` | :recycle: collapses to `native`, silently | :warning: ignored | :white_check_mark: |

**Why `openai` collapses silently.** In pipeline mode the realtime model already transcribes with
the same vendor and the same `gpt-4o-mini-transcribe`, so a separate OpenAI STT connection would add
cost and nothing else. No warning is logged because nothing is lost. (This also keeps pre-migration
rows working, where `assistant_stt_model="openai"` *meant* native transcription.)

**Why the degrade.** `cartesia`, `deepgram` and `elevenlabs` are plugin STTs with no parallel-tap
implementation for pipeline mode. Rather than start a call with no transcripts at all, `resolve_stt`
logs a warning and falls back to native transcription, so the caller still leaves with a transcript.
The selection is *stored* — switch the assistant to `cascade` and it takes effect with no further
edit. Same fallback applies in pipeline mode when a plugin provider is selected but no API key is
available.

**Cascade does not degrade.** In cascade mode a missing API key is fatal: `create_stt` returns `None`
and the job ends before the call connects. See [Failure modes](#failure-modes).

### Language codes are NOT portable between providers

The same spoken language is written differently per provider, and the standards do not overlap.
A code from the wrong standard is rejected at build time — logged, dropped, and the provider's
default applies — so a mis-set code degrades the call instead of breaking it.

| Provider | Standard | English | Hindi | Auto-detect |
|---|---|---|---|---|
| `sarvam` | BCP-47 Indic | `en-IN` | `hi-IN` | `unknown` (the default) |
| `cartesia` | ISO 639-1 | `en` | `hi` | :no_entry: none — unset means `en` |
| `deepgram` | BCP-47 | `en-US` | `hi-IN` | `multi`, and the default on `nova-3` / `flux-general-multi` |
| `elevenlabs` | **ISO 639-3** | `eng` | `hin` | omit the code (the default) — ~190 languages |
| `openai` | ISO 639-1 | `en` | `hi` | `detect_language`, turned on automatically when no code is set |

ElevenLabs is the one that bites. It is the only ISO 639-3 surface here, and upstream it does not
degrade: Scribe answers a BCP-47 code with `1008 invalid_request` and closes the socket, so the
agent retries the same failure for the length of the call and transcribes nothing.

Deepgram's `multi` is billed at a higher per-minute rate than a pinned language, so leaving the
field unset on `nova-3` costs more than setting it.

---

## Mode × TTS provider

`assistant_tts_model` + `assistant_tts_config`.

| Provider | `pipeline` | `realtime` | `cascade` |
|---|---|---|---|
| `cartesia` | :white_check_mark: | :warning: stored, never used | :white_check_mark: |
| `sarvam` | :white_check_mark: | :warning: stored, never used | :white_check_mark: |
| `elevenlabs` | :white_check_mark: | :warning: stored, never used | :white_check_mark: |
| `mistral` | :white_check_mark: | :warning: stored, never used | :white_check_mark: |
| omitted | :no_entry: `422` — both `assistant_tts_model` and `assistant_tts_config` are required | :white_check_mark: the model speaks its own audio | :no_entry: `422` — same requirement |

In `realtime` mode the model produces audio itself, so no TTS is built at all. Sending a TTS block
there is accepted (it is kept for the day you switch modes) but changes nothing about the call.

---

## Config keys ignored per mode

Accepted by validation, stored on the assistant, and read by nobody in that mode. None of these are
errors — they are the fields to stop debugging when a setting appears to have no effect.

| Field | Ignored in | Read in | Why |
|---|---|---|---|
| `assistant_llm_config.voice` | `pipeline`, `cascade` | `realtime` | Only the realtime model speaks its own audio; elsewhere the voice comes from the TTS provider. |
| `assistant_llm_config.temperature`, `max_output_tokens`, `reasoning_effort`, `service_tier`, `verbosity`, `tool_choice`, `parallel_tool_calls` | `pipeline`, `realtime` | `cascade` | These are `openai.responses.LLM` parameters, built only by `create_llm` in cascade mode. |
| `assistant_tts_model`, `assistant_tts_config` | `realtime` | `pipeline`, `cascade` | No TTS stage exists in realtime mode. |
| `assistant_stt_model`, `assistant_stt_config` | `realtime` | `pipeline`, `cascade` | The realtime model transcribes; there is no separate STT stage. |
| `assistant_stt_config.language` (Cartesia/Deepgram) | `pipeline` | `cascade` | The provider itself is cascade-only, so its whole config block is inert in pipeline mode. |
| `assistant_interaction_config.preferred_languages` | `cascade` | `pipeline`, `realtime` | It hints the *native* transcription prompt, and cascade has no native path. It is never sent to a speech provider as a language parameter in any mode — pin a language on `assistant_stt_config` instead. |

`assistant_stt_config.mode` (Sarvam) is **not** on this list: it is honoured in both pipeline and
cascade, and defaults to `codemix` in both.

---

## Failure modes

What a wrong combination actually looks like, in order of how early you find out.

| Symptom | Cause | Where |
|---|---|---|
| `422 Unprocessable Entity` at create, or at update when the request names `assistant_mode` | The rule table in `validate_mode_config` — bad provider, bad model for the mode, `native` STT in cascade, missing TTS pair | `src/api/models/api_schemas/config/llm_config.py` |
| `400 Bad Request` at update | The request is well-formed, but merged with what is already stored it produces an unrunnable assistant — e.g. `{"assistant_mode": "cascade"}` on a row holding `provider: "gemini"` or a non-allowlisted model | `enforce_stored_mode_constraints` in `src/api/routes/assistant.py` |
| Call connects, transcripts appear, but a knob you set does nothing | The field is ignored in this mode | [Config keys ignored per mode](#config-keys-ignored-per-mode) |
| Call connects, transcripts appear, but from a different engine than you chose | Cascade-only STT in pipeline mode, or a plugin STT with no API key — both degrade to `native` and log a warning | `resolve_stt`, `src/core/agents/stt/factory.py` |
| Call never starts. No error to the caller, one `ERROR` line in the worker log | A factory returned `None` and `entrypoint()` returned early: missing STT key in cascade, missing TTS key, unsupported TTS model, unsupported cascade LLM provider | `create_stt` / `create_tts` / `create_llm` |
| Call runs but produces no user transcripts | `realtime` + `gemini`: no `input_audio_transcription` is configured on the Gemini Live session | `src/core/agents/session.py` |
| Worker log: `Unknown assistant_mode '<x>' — treating as 'pipeline'` | `assistant_mode` was written outside the API (migration, direct Mongo edit). The DB field is a plain string with no enum. | `src/core/agents/session.py` |

Every one of these except the last two is now caught at the API. The remaining two are provider
limitations, not configuration errors.

---

## API keys

Per-assistant `api_key` fields always win; the environment variable is the fallback.

| Stage | Provider | `api_key` field | Environment fallback |
|---|---|---|---|
| LLM | openai | `assistant_llm_config.api_key` | `OPENAI_API_KEY` |
| LLM | gemini (realtime only) | `assistant_llm_config.api_key` | `GOOGLE_API_KEY` |
| STT | sarvam | `assistant_stt_config.api_key` | `SARVAM_API_KEY` |
| STT | cartesia | `assistant_stt_config.api_key` | `CARTESIA_API_KEY` |
| STT | deepgram | `assistant_stt_config.api_key` | `DEEPGRAM_API_KEY` |
| STT | elevenlabs | `assistant_stt_config.api_key` | `ELEVENLABS_API_KEY` |
| STT | openai (cascade) | `assistant_stt_config.api_key` | `OPENAI_API_KEY` |
| TTS | cartesia | `assistant_tts_config.api_key` | `CARTESIA_API_KEY` |
| TTS | sarvam | `assistant_tts_config.api_key` | `SARVAM_API_KEY` |
| TTS | elevenlabs | `assistant_tts_config.api_key` | `ELEVENLABS_API_KEY` |
| TTS | mistral | `assistant_tts_config.api_key` | `MISTRAL_API_KEY` |

!!! note "One key per vendor, two config fields"
    `ELEVENLABS_API_KEY` covers **both** ElevenLabs stages, STT and TTS — one variable, set it once.
    `SARVAM_API_KEY` and `CARTESIA_API_KEY` work the same way.

    The per-assistant fields are still separate, though: `assistant_stt_config.api_key` and
    `assistant_tts_config.api_key` are scoped to the provider selected for *that stage*. On an
    assistant with Sarvam STT and Cartesia TTS they hold two different vendors' keys, and crossing
    them fails auth — Sarvam answers `403` to a Cartesia key. Override a stage only when that stage's
    provider needs a different key from the system one.

Missing keys are now detected before the plugin is constructed, in both the STT and TTS factories, so
they always produce the "call never starts, one log line" failure above rather than an unhandled
exception.

---

## Unknown keys

Every provider config block is strict: an unrecognised key is a `422`, not a silent drop. This covers
`assistant_llm_config`, all four `assistant_tts_config` shapes (including `voice_settings`) and all
five `assistant_stt_config` shapes. A typo like `enable_diarisation` fails at create time instead of
quietly disabling the feature you thought you turned on.

The one thing that is *not* strict is the discriminator: `assistant_stt_config` may be omitted
entirely when `assistant_stt_model` is set, and the API fills in a defaults-only config for you.

---

## See also

- [Models & Providers](models.md) — every provider, model ID and config default.
- [Runtime Modes](../architecture/runtime-modes.md) — what each mode is and how to pick one.
- [Cascade Pipeline](../architecture/cascade-pipeline.md) — the three-stage mode in depth.
- [Create Assistant](../api/assistant/create.md) — request shape and per-mode examples.
