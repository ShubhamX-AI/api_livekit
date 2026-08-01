# Models & Providers

Single reference for every model, provider, and config default the runtime actually uses — sourced
from the factories in `src/core/agents/{llm,stt,tts}/factory.py` and `src/core/agents/session.py`, not
from any other doc. If this page and another doc disagree, this page is correct; file an issue against
the other one.

`assistant_mode` selects the *shape* of the session (`pipeline`, `realtime`, `cascade`) — see
[Runtime Modes](../architecture/runtime-modes.md). This page covers what each stage of each mode can
actually be configured to run.

## Realtime LLM (`pipeline` and `realtime` modes)

Both modes route through a realtime model — `pipeline` uses it in text-only mode with an external TTS,
`realtime` lets it speak its own audio. Configured via `assistant_llm_config`.

| Field | Values | Default |
|---|---|---|
| `provider` | `gemini`, `openai` | `gemini` in `realtime` mode, `openai` in `pipeline` mode |
| `model` | any provider model string | `gemini-3.1-flash-live-preview` (gemini), `gpt-realtime-1.5` (openai) |
| `voice` | provider voice name | `Puck` (gemini), `marin` (openai). **Honored only in `realtime` mode** — `pipeline` mode emits text, so voice is meaningless there and the field is silently ignored. |
| `api_key` | string | falls back to system `GOOGLE_API_KEY` / `OPENAI_API_KEY` |

OpenAI realtime additionally runs fixed turn-taking params not exposed to the API: `TurnDetection(type="semantic_vad", eagerness="high", create_response=True, interrupt_response=False)`, and
`RealtimeTruncationRetentionRatio(retention_ratio=0.75, post_instructions=8000)`.

Native user-transcription (`assistant_stt_model="native"`, pipeline mode only) uses OpenAI
`gpt-4o-mini-transcribe` regardless of which realtime provider is selected.

## Cascade LLM (`cascade` mode only)

Built by `create_llm` (`src/core/agents/llm/factory.py`) as `openai.responses.LLM` — cheaper than
chat-completions, same `@function_tool` contract. Configured via `assistant_llm_config`.

| Field | Values | Default |
|---|---|---|
| `provider` | `openai` only — any other value is rejected | `openai` |
| `model` | any OpenAI chat model string (free-form, not an enum — new OpenAI models work without a deploy; an unknown name fails at the first API call, not at assistant creation) | `gpt-4.1` |
| `api_key` | string | falls back to system `OPENAI_API_KEY` |

Models known to work: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini`, `gpt-5`,
`gpt-5-mini`, `gpt-5-nano`, `gpt-5.1`, `gpt-5.2`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.5`,
`chatgpt-4o-latest`.

## STT

`assistant_stt_model` + `assistant_stt_config`. Two different code paths read the same fields:
`resolve_stt` (pipeline mode's parallel Sarvam tap) and `create_stt` (cascade's session STT stage) — they
don't always agree, see the quirks below.

| Provider | Valid in | Model default | Other config |
|---|---|---|---|
| `sarvam` | `pipeline` (default), `cascade` | `saaras:v3` (also `saaras:v2.5`, `saarika:v2.5`) | `language` default `unknown` (auto-detect); `mode` default `codemix` (also `transcribe`, `translate`, `verbatim`, `translit`, cascade only honors this — see quirks) |
| `cartesia` | `cascade` only | `ink-whisper` (43 languages) or `ink-2` (English only) | `language` fixed, no auto-detect; falls back to `assistant_interaction_config.preferred_languages[0]`, then `en` |
| `native` | `pipeline` only — rejected in `cascade` (no realtime model to self-transcribe) | n/a (the conversational LLM transcribes itself: `gpt-4o-mini-transcribe`) | no config |

Ignored entirely in `realtime` mode (the model always transcribes itself).

**Quirks worth knowing before you rely on them:**

- A stored legacy value `assistant_stt_model="openai"` is silently rewritten to `"native"` at resolve
  time — old data, not a documented option to send.
- If `sarvam` is selected with no API key available (neither in config nor `SARVAM_API_KEY`), pipeline
  mode silently degrades to `native` rather than erroring.
- The pipeline-mode parallel Sarvam tap **hardcodes `mode="codemix"`** — the `mode` config key only
  takes effect in `cascade`. Sending a different `mode` in pipeline mode is accepted but has no effect.
- Sarvam's `codemix` + `language="unknown"` combination is the multilingual one: auto-detects and keeps
  code-switching intact inside a single utterance. 24 language codes: `as`, `bn`, `brx`, `doi`, `en`,
  `gu`, `hi`, `kn`, `kok`, `ks`, `mai`, `ml`, `mni`, `mr`, `ne`, `od`, `pa`, `sa`, `sat`, `sd`, `ta`, `te`,
  `ur` (all `-IN`), plus `unknown`.
- Cartesia's 43 `ink-whisper` codes: `en`, `de`, `es`, `fr`, `ja`, `pt`, `zh`, `hi`, `ko`, `it`, `nl`,
  `pl`, `ru`, `sv`, `tr`, `tl`, `bg`, `ro`, `ar`, `cs`, `el`, `fi`, `hr`, `ms`, `sk`, `da`, `ta`, `uk`,
  `hu`, `no`, `vi`, `bn`, `th`, `he`, `ka`, `id`, `te`, `gu`, `kn`, `ml`, `mr`, `or`, `pa`.

## TTS

`assistant_tts_model` + `assistant_tts_config`. The synthesis **model is hardcoded per provider and not
configurable** — `assistant_tts_config` has no `model` key.

| Provider | Model (fixed) | Required config | Fixed synthesis params |
|---|---|---|---|
| `cartesia` | `sonic-3` | `voice_id` | `speed=1.0` |
| `sarvam` | `bulbul:v3` | `speaker` | `pace=1.0`, `speech_sample_rate=24000`, `temperature=0.3`, `min_buffer_size=30`, `max_chunk_length=50` |
| `elevenlabs` | `eleven_v3` | `voice_id` | non-streaming (HTTP chunked) |
| `mistral` | `voxtral-mini-tts-2603` | `voice_id` | `response_format="opus"`, non-streaming |

All four accept an optional `api_key`, falling back to the matching system key
(`CARTESIA_API_KEY` / `SARVAM_API_KEY` / `ELEVENLABS_API_KEY` / `MISTRAL_API_KEY`).

**Sarvam `target_language_code` default mismatch:** the API schema default is `bn-IN`, but the factory's
own fallback for a config stored without the key is `en-IN`. Set it explicitly rather than relying on
either default.

## VAD & turn detection (`cascade` mode only)

`pipeline` and `realtime` modes rely on the realtime model's own server-side VAD. `cascade` has no
realtime model, so the session builds its own:

- `inference.VAD(model="silero", min_silence_duration=0.4)` — in-process native binding, weights ship in
  `livekit-local-inference`. No API key, no network call.
- `inference.TurnDetector(version="v1-mini")` — local end-of-utterance model, weights ship in the wheel.
  Pinned deliberately: unpinned, the SDK tries the Cloud-only `v1` first. 14 languages including Hindi.

**Self-hosted constraint:** `inference.TurnDetector(version="v1")` and `interruption={"mode": "adaptive"}`
require LiveKit Cloud and are not usable here — only `v1-mini` and `{"mode": "vad"}` are local. Full
detail in [Cascade Pipeline](../architecture/cascade-pipeline.md#turn-detection).

## Internal models (not user-selectable, still billed)

| Feature | Model | Where |
|---|---|---|
| Filler words (`assistant_interaction_config.filler_words`) | `gpt-4o-mini` | `src/core/agents/voice_features.py` |
| Native user-transcription (pipeline mode, `assistant_stt_model="native"`) | `gpt-4o-mini-transcribe` | `src/core/agents/session.py` |

These run regardless of your chosen LLM/TTS provider and add their own token cost.
