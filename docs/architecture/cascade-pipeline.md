# Cascade Pipeline (STT → LLM → TTS)

`assistant_mode="cascade"` runs a **true three-stage pipeline**: a plugin STT, a plain
(non-realtime) LLM, and a plugin TTS. Each stage is a separate model, separately billed and
independently swappable.

This is the mode to pick when you need per-component cost visibility, cheap text models, or a
specific STT provider. The other two modes are documented in [Runtime Modes](runtime-modes.md).
For the model IDs and config keys used below, see [Models & Providers](../reference/models.md).

## Why it exists

`pipeline` mode is really a *half*-cascade: a realtime model does STT **and** LLM in one
opaque billing unit, and only TTS is separate. That has three consequences:

1. **No cost breakdown.** A realtime model bills one audio-token stream. You cannot tell what
   transcription cost versus reasoning.
2. **No cheap models.** The LLM must be a realtime model; `gpt-4.1-mini` is unreachable.
3. **STT is a side channel.** The Sarvam tap opens its own audio stream outside the SDK's
   pipeline, because the `stt=` slot was never used.

Cascade fixes all three by giving the session a real STT stage.

```
pipeline (half-cascade)     realtime                cascade (true pipeline)
─────────────────────       ──────────────          ───────────────────────
 caller audio                caller audio            caller audio
      │                           │                       │
 ┌────▼─────┐  (+ Sarvam     ┌────▼─────┐            ┌────▼────┐
 │ realtime │   tap on the   │ realtime │            │   STT   │  sarvam | cartesia
 │  model   │   side for     │  model   │            └────┬────┘
 │ STT+LLM  │   transcripts) │STT+LLM+  │            ┌────▼────┐
 └────┬─────┘                │   TTS    │            │   LLM   │  openai
 ┌────▼─────┐                └────┬─────┘            └────┬────┘
 │   TTS    │                     │                  ┌────▼────┐
 └────┬─────┘                     │                  │   TTS   │  4 providers
      ▼                           ▼                  └────┬────┘
  agent audio                agent audio                  ▼
                                                      agent audio
```

## Configuration

```json
{
  "assistant_name": "Cascade Agent",
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
    "model": "gpt-4.1-mini"
  },
  "assistant_tts_model": "cartesia",
  "assistant_tts_config": {
    "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
  }
}
```

Validation rules specific to cascade:

| Rule | Why |
|---|---|
| `assistant_tts_model` + `assistant_tts_config` required | The LLM emits text only; something must speak it. |
| `assistant_stt_model` must be `sarvam` or `cartesia` | `native` means "the realtime model transcribes itself" — cascade has no realtime model. |
| `assistant_llm_config.provider` must be `openai` or unset | Only OpenAI is wired up as a non-realtime LLM. |

## STT stage

Built by `create_stt` in `src/core/agents/stt/factory.py`. Both providers are streaming.

### sarvam — the multilingual default

| Config key | Default | Values |
|---|---|---|
| `model` | `saaras:v3` | see [Models & Providers](../reference/models.md#stt) |
| `language` | `unknown` | `unknown` = **auto-detect**, or a fixed BCP-47 code |
| `mode` | `codemix` | see [Models & Providers](../reference/models.md#stt) |
| `api_key` | system `SARVAM_API_KEY` | per-assistant override |

**This is the only genuinely multilingual option.** `language="unknown"` auto-detects, and
`mode="codemix"` keeps code-switching intact *inside a single utterance* — a caller who says a
Hindi sentence with English nouns is transcribed in both scripts correctly. Full list of the 24
`-IN` language codes: [Models & Providers](../reference/models.md#stt).

The other modes: `transcribe` gives a plain transcript, `translate` returns English,
`verbatim` keeps filler words and repetitions, `translit` romanises Indic script.

### cartesia — single fixed language

| Config key | Default | Values |
|---|---|---|
| `model` | `ink-whisper` | see [Models & Providers](../reference/models.md#stt) |
| `language` | `en` | one fixed code — **no auto-detect** |
| `api_key` | system `CARTESIA_API_KEY` | per-assistant override |

Cartesia STT cannot detect language: you pick one code and it transcribes that. Use Sarvam for
any call where the caller might switch languages.

`model` is pinned explicitly in the factory rather than left to the plugin default, because
that default flipped from `ink-whisper` to the English-only `ink-2` in `livekit-agents` 1.5.15.
`ink-whisper`'s 43 language codes: [Models & Providers](../reference/models.md#stt).

## LLM stage

Built by `create_llm` in `src/core/agents/llm/factory.py`, using
`openai.responses.LLM` — the recommended surface for the direct OpenAI API (cheaper than
chat-completions, and the same `@function_tool` contract, so DB-backed tools work unchanged).

| Config key | Default | Notes |
|---|---|---|
| `provider` | `openai` | Only `openai` is supported in cascade |
| `model` | `gpt-4.1` | Any OpenAI chat model; known-good list in [Models & Providers](../reference/models.md#cascade-llm-cascade-mode-only) |
| `api_key` | system `OPENAI_API_KEY` | per-assistant override |

`model` is deliberately a free-form string, not an enum: OpenAI ships models continuously and
an enum would mean a deploy per model. An unknown name fails at the first API call, not at
assistant creation.

## TTS stage

Unchanged from `pipeline` mode — all four providers work identically. See
[create](../api/assistant/create.md) for the per-provider config and
[Models & Providers](../reference/models.md#tts) for the fixed model IDs and synthesis params.

## Turn detection

Cascade has no realtime model, so there is no server-side VAD to defer to — endpointing and
interruption are the session's own job:

```python
AgentSession(
    stt=cascade_stt,
    llm=llm,
    tts=tts,
    vad=inference.VAD(model="silero", min_silence_duration=0.4),
    turn_handling=TurnHandlingOptions(
        turn_detection=inference.TurnDetector(version="v1-mini"),
        endpointing={"mode": "dynamic", "min_delay": 0.3, "max_delay": 1.0},
        interruption={"mode": "vad", "min_duration": 0.5,
                      "false_interruption_timeout": 2.0,
                      "resume_false_interruption": True},
    ),
)
```

**Everything here runs locally — this is a self-hosted deployment.**

- `inference.VAD(model="silero")` is an in-process native binding shipped in
  `livekit-local-inference`, a core SDK dependency. No API key, no network call, nothing to
  prewarm. `min_silence_duration` is raised from the `0.25` default to clear the turn
  detector's `0.25` floor with margin.
- `inference.TurnDetector(version="v1-mini")` is an audio end-of-utterance model whose weights
  ship inside the wheel. The version is **pinned** on purpose: left unpinned the SDK tries the
  Cloud-only `v1` first whenever `LIVEKIT_DEV_MODE` is set, then falls back with a warning.
  14 languages including Hindi.
- `interruption={"mode": "vad"}` — the `adaptive` mode is LiveKit Cloud-only and is silently
  disabled in production, with no local fallback.

Unlike the `pipeline` branch, these interruption knobs are **live**: there is no realtime-model
VAD short-circuiting them.

Note that `SpeechGate` ([Audio Pipeline](audio-pipeline.md#input-speech-gate)) already runs a
vendored Silero ONNX over the same audio for noise gating, so a cascade call runs VAD twice —
once to gate noise upstream, once to endpoint. Correct, but it costs some worker CPU.

## Per-component usage

The reason the mode exists. `src/core/agents/usage.py::summarize_usage` reads
`session.usage`, which reports one typed entry per `(provider, model)` pair, and folds it into
flat `UsageRecord` fields:

| Field | Populated in |
|---|---|
| `llm_model`, `llm_input_*`, `llm_output_*`, `llm_total_tokens` | all modes |
| `tts_characters_count`, `tts_audio_duration` | `pipeline`, `cascade` |
| `stt_provider`, `stt_model`, `stt_audio_duration` | **`cascade` only** |

STT fields stay empty in the other modes because their transcription happens *inside* the LLM
and the spend is already inside its token counts — there is nothing separate to attribute.

These values are raw usage metrics, not costs. Apply your own provider rates downstream. They
reach you three ways: the [end-of-call webhook](../api/calls/webhook.md), the
`usage_records` collection, and the admin analytics endpoints
([summary](../api/admin/token-summary.md),
[by user](../api/admin/tokens-by-user.md),
[by assistant](../api/admin/tokens-by-assistant.md)).

All aggregation is in-process; no Cloud call is involved.

## Text-only cascade

`cascade` + `text_only: true` on a [web call](../api/calls/web-call.md) gives a pure text
chatbot on a plain chat model — no STT, no TTS, no VAD instantiated. Cheaper than the same
chatbot on a realtime model. `realtime` mode still rejects `text_only`.

## Feature compatibility

Every pre-existing runtime feature works in cascade. Three needed a cascade-specific
code path, because they were written against a realtime model:

| Feature | Cascade behaviour |
|---|---|
| Prerecorded greeting audio | Unchanged — `session.say(audio=...)` is provider-agnostic |
| Speaks-first / `assistant_start_instruction` | Unchanged — takes the same `generate_reply(instructions=...)` path as pipeline |
| `allow_interruptions=False` on the greeting | **Better than pipeline.** The knob is genuinely live here; pipeline mode's realtime VAD interrupts regardless |
| SpeechGate denoiser / noise cancellation | Unchanged — attached via `RoomOptions`, independent of mode |
| Input guard (blanking at reply start) | Unchanged — mutes through `SpeechGate` |
| Silence watchdog | Unchanged — takes the `session.say` path (`use_llm_for_speech=False`) |
| Filler words | Enabled, same as pipeline. Needs an external TTS, which cascade has |
| Hold / background sound / thinking sound | Unchanged. The thinking sound is *more* audible here, since a real LLM TTFT replaces a realtime model's instant stream |
| Recording (egress), call-readiness gate | Unchanged — mode-agnostic |
| Max call duration watchdog | Unchanged |
| DB-backed function tools | Unchanged — `openai.responses.LLM` honours the same `@function_tool` contract |
| Transcripts | Written exactly once, via `conversation_item_added`. The Sarvam tap is off, so there is no double-write |
| Sarvam TTS keepalive | Runs whenever the TTS is Sarvam, same as pipeline |
| **`end_call` tool** | **Cascade-specific path.** A non-realtime LLM continues in the *same* speech handle across tool steps, so the goodbye has already played by the time the done-callback fires. The `speech_created` wait that realtime needs is skipped — leaving it in burned 5 s of dead air before hangup |
| **Exotel pre-answer window** | **Cascade-specific path.** Pipeline disables the realtime model's server VAD so ring-tone RTP cannot open a spurious turn. Cascade has no such model, so the input is blanked through `SpeechGate.muted` for the duration of the gate wait instead |
| **`preferred_languages`** | Honoured differently per provider. Sarvam needs nothing — `language="unknown"` auto-detects every language the list could name. Cartesia cannot auto-detect, so an unpinned `language` falls back to the first preferred language, then `en` |

Two consequences worth knowing:

- The native STT prompt (`build_native_stt_prompt`) and `input_audio_noise_reduction` are
  **Realtime-API parameters and do not apply** in cascade. Transcription quality is the STT
  provider's own; noise handling is `SpeechGate`'s.
- `text_only: true` on a cascade assistant takes the no-audio branch, so no STT, TTS or VAD is
  constructed at all.

## What cascade does not use

- **The Sarvam parallel tap.** Its STT is a first-class session stage, so transcripts arrive
  through `conversation_item_added` like any other. The tap remains for `pipeline` mode.
- **`turn_detection="realtime_llm"`.** No realtime model to detect turns.
- **`input_audio_transcription` / native STT prompts.** Those are Realtime-API parameters.
