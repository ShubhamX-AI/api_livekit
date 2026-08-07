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
| `provider` | `openai` in `pipeline` mode (`gemini` is rejected — see [Compatibility Matrix](compatibility.md#mode-llm-provider)); `gemini` or `openai` in `realtime` mode | `gemini` in `realtime` mode, `openai` in `pipeline` mode |
| `model` | OpenAI: one of `OPENAI_REALTIME_MODELS` (validated). Gemini: any Live model string (not validated) | `gemini-3.1-flash-live-preview` (gemini), `gpt-realtime-1.5` (openai) |
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
| `model` | one of the documented model IDs below — **validated against the allowlist at creation/update time** | `gpt-4.1` |
| `api_key` | string | falls back to system `OPENAI_API_KEY` |
| `temperature` | `0.0`–`2.0` | SDK default (`0.8`) |
| `max_output_tokens` | positive int | unset (model default) |
| `reasoning_effort` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` | unset |
| `service_tier` | `auto`, `default`, `flex`, `scale`, `priority` | unset |
| `verbosity` | `low`, `medium`, `high` | unset |
| `tool_choice` | `auto`, `required`, `none` | unset |
| `parallel_tool_calls` | bool | unset |

### Documented models

| Model | Notes |
|---|---|
| `gpt-4.1` | default; general-purpose text model |
| `gpt-4.1-mini`, `gpt-4.1-nano` | cheaper, faster text models |
| `gpt-4o`, `gpt-4o-mini` | multimodal legacy chat models |
| `gpt-5` | reasoning model — ignores `temperature`, uses `reasoning_effort` |
| `gpt-5-mini`, `gpt-5-nano` | reasoning models, smaller + cheaper |
| `gpt-5.1`, `gpt-5.1-chat-latest` | reasoning models |
| `gpt-5.2`, `gpt-5.2-chat-latest` | reasoning models |
| `gpt-5.3-chat-latest` | reasoning model |
| `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano` | reasoning models |
| `gpt-5.5` | reasoning model |
| `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` | reasoning models |
| `chat-latest` | auto-follows the latest `gpt-5.x-chat` snapshot |
| `gpt-oss-120b` | open-weight model, non-reasoning |

**Reasoning-model rule:** the `gpt-5`/`gpt-5.x` line rejects `temperature` and prefers
`reasoning_effort`. `temperature` is ignored there; send `reasoning_effort` instead.

### On the allowlist

The mode validator (`validate_mode_config` in `src/api/models/api_schemas/config/llm_config.py`) rejects
any `model` outside the table above with a `422`. When OpenAI ships a new model, add it to
`OPENAI_CASCADE_MODELS` in that file and to the table above.

The pipeline and realtime modes have their own, separate allowlist (`OPENAI_REALTIME_MODELS`) of
OpenAI **realtime** model IDs — the two sets do not overlap, and sending a chat model such as
`gpt-4.1` in pipeline mode is a `422`. Gemini realtime model IDs stay free-form. Full table:
[Compatibility Matrix → Model IDs](compatibility.md#model-ids).

## STT

`assistant_stt_model` + `assistant_stt_config`. Two different code paths read the same fields:
`resolve_stt` (pipeline mode's parallel Sarvam tap) and `create_stt` (cascade's session STT stage) — they
don't always agree, see the quirks below.

| Provider | Valid in | Model default | Other config |
|---|---|---|---|
| `sarvam` | `pipeline` (default), `cascade` | `saaras:v3` (also `saaras:v2.5`, `saarika:v2.5`) | `language` default `unknown` (auto-detect); `mode` default `codemix` (also `transcribe`, `translate`, `verbatim`, `translit`; honoured in both pipeline and cascade) |
| `cartesia` | `cascade` only | `ink-whisper` (43 languages) or `ink-2` (English only) | `language` fixed, no auto-detect; falls back to `assistant_interaction_config.preferred_languages[0]`, then `en` |
| `deepgram` | `cascade` only | `nova-3` (multilingual, 45 languages); also `nova-2`, `flux-general-en` (English), `flux-general-multi` | `language` BCP-47 or `multi` (explicit auto-detect; omitted — falls back to `preferred_languages`, then `en`); `enable_diarization` (bool, default `false` — omitted stays **off**, never force-enabled); `keyterm` (string or list — omitted — not sent, no biasing); `api_key` falls back to system `DEEPGRAM_API_KEY` |
| `elevenlabs` | `cascade` only | `scribe_v2_realtime` (auto-detects ~190 languages); also `scribe_v2`, `scribe_v1` | `language_code` BCP-47 (omit = auto-detect; falls back to `preferred_languages`, then auto-detect); `no_verbatim` (bool, default `false` — omitted keeps fillers); `api_key` falls back to system `ELEVENLABS_API_KEY` — the same variable the ElevenLabs TTS provider uses |
| `native` | `pipeline` only — rejected in `cascade` (no realtime model to self-transcribe) | n/a (the conversational LLM transcribes itself: `gpt-4o-mini-transcribe`) | no config |

Ignored entirely in `realtime` mode (the model always transcribes itself).

**Quirks worth knowing before you rely on them:**

- A stored legacy value `assistant_stt_model="openai"` is silently rewritten to `"native"` at resolve
  time — old data, not a documented option to send.
- If `sarvam` is selected with no API key available (neither in config nor `SARVAM_API_KEY`), pipeline
  mode silently degrades to `native` rather than erroring.
- The `mode` config key is honoured in **both** pipeline and cascade, and defaults to `codemix` in
  both. (Earlier builds hardcoded `codemix` in the pipeline tap and ignored the field there.)
- Sarvam's `codemix` + `language="unknown"` combination is the multilingual one: auto-detects and keeps
  code-switching intact inside a single utterance. 24 language codes: `as`, `bn`, `brx`, `doi`, `en`,
  `gu`, `hi`, `kn`, `kok`, `ks`, `mai`, `ml`, `mni`, `mr`, `ne`, `od`, `pa`, `sa`, `sat`, `sd`, `ta`, `te`,
  `ur` (all `-IN`), plus `unknown`.
- Cartesia's 43 `ink-whisper` codes: `en`, `de`, `es`, `fr`, `ja`, `pt`, `zh`, `hi`, `ko`, `it`, `nl`,
  `pl`, `ru`, `sv`, `tr`, `tl`, `bg`, `ro`, `ar`, `cs`, `el`, `fi`, `hr`, `ms`, `sk`, `da`, `ta`, `uk`,
  `hu`, `no`, `vi`, `bn`, `th`, `he`, `ka`, `id`, `te`, `gu`, `kn`, `ml`, `mr`, `or`, `pa`.

### STT configs explained

Every field in `assistant_stt_config`, per provider. "Omitted" means the key is absent from
the config dict. `api_key` resolution: a per-assistant `api_key` in the config always beats
the env var; if **both** are missing, a cascade assistant aborts (`create_stt` returns `None`,
logged — it does **not** silently fall back), while pipeline selection of a cascade-only
provider (cartesia / deepgram / elevenlabs) degrades to native transcription with a warning.

| Provider | Channel (config key) | Default | Meaning | What changes if you change it |
|---|---|---|---|---|
| `sarvam` | `model` | `saaras:v3` | which Saras model transcribes | `saaras:v2.5` or `saarika:v2.5` swap the model; omitted keeps the default |
| `sarvam` | `language` | `unknown` | `unknown` = auto-detect, keeps code-switching with `codemix` | a BCP-47 code locks one fixed language; omitted stays auto-detect |
| `sarvam` | `mode` | `codemix` | transcription style (`codemix`, `transcribe`, `translate`, `verbatim`, `translit`) | **cascade only** honors it; pipeline hardcodes `codemix` and ignores this key |
| `sarvam` | `api_key` | system `SARVAM_API_KEY` | auth for the STT call | per-assistant override wins; both missing → **pipeline** falls back to `native` (warning), **cascade** aborts |
| `cartesia` | `model` | `ink-whisper` (pinned in factory) | 43-language STT model | `ink-2` is English only; the factory pins the model explicitly so the plugin's own default flip can't bite |
| `cartesia` | `language` | first `preferred_languages` entry, then `en` | exactly one fixed language — **no auto-detect** | set a code to pin it; omitted falls back to the preferred list, then `en` |
| `cartesia` | `api_key` | system `CARTESIA_API_KEY` | auth | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `deepgram` | `model` | `nova-3` | multilingual, 45 languages | `nova-2`, `flux-general-en` (English only), `flux-general-multi`; omitted keeps the default |
| `deepgram` | `language` | first `preferred_languages` entry, then `en` | `multi` = auto-detect; BCP-47 = fixed | set `multi` to auto-detect or a code to pin; omitted falls back to the preferred list, then `en` |
| `deepgram` | `enable_diarization` | `false` | label each utterance with its speaker (nova models) | `true` turns it on; **omitted stays `false`, never force-enabled** |
| `deepgram` | `keyterm` | not sent | bias recognition toward a term | a string/list biases recognition (`nova-3`/`flux` only); **omitted — the key is not sent, no biasing** |
| `deepgram` | `api_key` | system `DEEPGRAM_API_KEY` | auth | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `elevenlabs` | `model` | `scribe_v2_realtime` | auto-detects ~190 languages | `scribe_v2`, `scribe_v1`; omitted keeps the default |
| `elevenlabs` | `language_code` | omitted = auto-detect; else first `preferred_languages` entry | BCP-47 pins one language; omitting enables auto-detect | set a code to pin (**disables auto-detect**); omit to auto-detect (or first preferred language) |
| `elevenlabs` | `no_verbatim` | `false` | strip filler words from the transcript when `true` | `true` strips fillers; **omitted stays `false` — fillers kept** |
| `elevenlabs` | `api_key` | system `ELEVENLABS_API_KEY` | auth — one variable covers both the STT and TTS stages | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |

`native` (pipeline only) takes no config — the conversational LLM transcribes itself
(`gpt-4o-mini-transcribe`).

### STT pitfalls & what not to combine

These are the easy-to-miss traps. All statements match the plugin behaviour in LiveKit Agents.

- **`keyterm` (Deepgram) is ignored on `nova-2`.** Nova-2 uses a different keyword mechanism
  (`keywords` keyword pairs), not `keyterm`. Sending `keyterm` with `model: "nova-2"` does nothing.
  It is honoured by `nova-3` and both `flux` models only.
- **`enable_diarization` is meaningful only on **nova** models.** Pairing it with `flux-general-en` /
  `flux-general-multi` logs a warning and is dropped; omitting it never force-enables diarization.
- **The two Deepgram families use different APIs, and the factory picks for you.** `nova-*` runs on
  Deepgram's `/listen/v1` (`deepgram.STT`); `flux-*` runs on the turn-based `/listen/v2`
  (`deepgram.STTv2`) and brings its own endpointing. Selecting a `flux` model is enough — no other
  config changes. On flux, `language` becomes a *hint* rather than a pin, and Deepgram itself ignores
  the hint on `flux-general-en` (English-only by definition).
- **Don't pin a language a model can't speak.** `flux-general-en` is English-only — setting
  `language` to `multi` or a non-English BCP-47 code on it is invalid. Use `flux-general-multi` for
  multilingual. A `language` code that isn't in the model's list is ignored / falls back.
- **`multi` means auto-detect; you can't both pin and detect.** `language: "multi"` (Deepgram nova
  models) tells the model to detect the language of each segment on its own. It is the *no-pin*
  mode — it is not a language code and it cannot be combined with one. Pick either a specific
  BCP-47 code or `multi`, never a mix of the two.
- **Fallback asymmetry — the big one for phone callers.** When `language`/`language_code` is omitted,
  the providers **do not all auto-detect**:
  - `elevenlabs`: falls back to `preferred_languages[0]`, else the provider auto-detects (~190 langs) — safe for multilingual.
  - `deepgram`: falls back to `preferred_languages[0]`, else **`en`** (NOT `multi`). A caller switching to a language you didn't list lands on English → mis-transcribed. Prefer setting `language: "multi"` when callers may be multilingual.
  - `sarvam` (`unknown`) and `cartesia` (pinned) differ again — never assume a uniform default.
- **Pinning `language_code` (ElevenLabs) disables auto-detect.** `omit` → auto-detect; `set` → pinned & detection off. So a caller who switches languages mid-call is mis-transcribed once pinned. Set it only when a fixed language is guaranteed.
- **One `ELEVENLABS_API_KEY` covers both stages,** STT and TTS. The per-assistant fields stay separate, though: `assistant_stt_config.api_key` and `assistant_tts_config.api_key` are scoped to whichever provider that stage selected, so on a mixed assistant they hold two different vendors' keys. Sending one vendor's key on another vendor's path fails auth (Sarvam answers `403`).
- **Missing key in cascade aborts (no fallback).** If neither a config `api_key` nor the system env var is present, `create_stt` returns `None` and the cascade job is abandoned (logged) — it does **not** silently switch models. In `pipeline` mode the same selection only degrades to `native` transcription with a warning.
- **Multilingual billing.** Deepgram `language: "multi"` (and any multilingual detection) is billed at a higher per-minute rate than monolingual. Factor this in before enabling it broadly.

## TTS

`assistant_tts_model` + `assistant_tts_config`. The synthesis **model is hardcoded per provider
except ElevenLabs** (which now accepts a `model` key). Synthesis params are configurable via
`assistant_tts_config`.

| Provider | Model (default) | Required config | Configurable synthesis params |
|---|---|---|---|
| `cartesia` | `sonic-3` (fixed) | `voice_id` | `language` (default `en`), `speed` (float `0`–`3`, default `1.0`), `volume` (default `1.0`), `emotion`, `pronunciation_dict_id` |
| `sarvam` | `bulbul:v3` (fixed) | `speaker` | `target_language_code` (default `en-IN`), `pace` (`0.3`–`3.0`, default `1.0`), `speech_sample_rate` (one of `8000`/`16000`/`22050`/`24000`/`32000`/`44100`/`48000`, default `24000`), `temperature` (`0.01`–`2.0`, default `0.3`) |
| `elevenlabs` | `eleven_v3` (default) | `voice_id` | `model` (`eleven_v3`, `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`), `voice_settings` (`stability`, `similarity_boost`, `style`, `speed`, `use_speaker_boost`); non-streaming (HTTP chunked) |
| `mistral` | `voxtral-mini-tts-2603` (fixed) | `voice_id` | `response_format="opus"`, non-streaming |

All four accept an optional `api_key`, falling back to the matching system key
(`CARTESIA_API_KEY` / `SARVAM_API_KEY` / `ELEVENLABS_API_KEY` / `MISTRAL_API_KEY`).

Speed is therefore **configurable per assistant** for Cartesia, Sarvam and ElevenLabs (the three
providers whose SDK exposes a rate knob). See each tab in [create](../api/assistant/create.md) for
valid ranges.

**Sarvam `target_language_code` defaults to `en-IN`.** Omitting it stores `null`, and the factory
substitutes `en-IN`. (Earlier builds defaulted the schema to `bn-IN`, which silently overrode the
factory fallback and synthesized Bengali for every assistant that left the field out. Assistants
created before this fix have `bn-IN` written into their stored config — send the field explicitly to
correct them.)

**Unknown keys are rejected.** Every TTS config block — and the nested ElevenLabs `voice_settings` —
is strict: an unrecognised key returns `422` rather than being silently dropped. The same is true of
`assistant_stt_config` and `assistant_llm_config`. This catches typos such as `speaking_rate` or
`enable_diarisation` at create time.

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
