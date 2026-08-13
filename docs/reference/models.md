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

The truncation half is **sent only to the `gpt-realtime*` line**. `session.truncation` is a GA
Realtime API field that `gpt-4o-realtime-preview` and `gpt-4o-mini-realtime-preview` do not have,
and the API errors on an unknown session field instead of ignoring it. On those two models the
session runs without the context cap and logs one line saying so — see
[Runtime Modes → LLM Context Truncation](../architecture/runtime-modes.md#llm-context-truncation).

Native user-transcription (`assistant_stt_model="native"`, pipeline mode only) uses OpenAI
`gpt-4o-mini-transcribe` regardless of which realtime provider is selected.

In `realtime` mode both vendors transcribe the caller: OpenAI is given
`gpt-4o-mini-transcribe` explicitly, and Gemini transcribes with its own model because the
Google plugin enables `input_audio_transcription` whenever the argument is omitted. Neither
needs `assistant_stt_model` — that field is ignored in this mode.

## Cascade LLM (`cascade` mode only)

Built by `create_llm` (`src/core/agents/llm/factory.py`) as `openai.responses.LLM` — cheaper than
chat-completions, same `@function_tool` contract. Configured via `assistant_llm_config`.

| Field | Values | Default |
|---|---|---|
| `provider` | `openai` only — any other value is rejected | `openai` |
| `model` | one of the documented model IDs below — **validated against the allowlist at creation/update time** | `gpt-4.1` |
| `api_key` | string | falls back to system `OPENAI_API_KEY` |
| `temperature` | `0.0`–`2.0` — **chat models only** | SDK default (`0.8`) |
| `max_output_tokens` | positive int | unset (model default) |
| `reasoning_effort` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` — **reasoning models only** | unset |
| `service_tier` | `auto`, `default`, `flex`, `scale`, `priority` | unset |
| `verbosity` | `low`, `medium`, `high` — **gpt-5 generation only** | unset |
| `tool_choice` | `auto`, `required`, `none` | unset |
| `parallel_tool_calls` | bool | unset |

Three of those knobs are model-gated; sending one to a model that does not read it is a
`400` from OpenAI on **every** turn of the call, not a warning. Pairing a knob with a model
that rejects it is a `422` at create/update. Full matrix:
[Compatibility Matrix → Cascade LLM knobs](compatibility.md#cascade-llm-knobs).

### Documented models

| Model | Family | Notes |
|---|---|---|
| `gpt-4.1` | chat | default; general-purpose text model |
| `gpt-4.1-mini`, `gpt-4.1-nano` | chat | cheaper, faster text models |
| `gpt-4o`, `gpt-4o-mini` | chat | multimodal legacy chat models |
| `gpt-5` | reasoning | rejects `temperature`, takes `reasoning_effort` |
| `gpt-5-mini`, `gpt-5-nano` | reasoning | smaller + cheaper |
| `gpt-5.1` | reasoning | |
| `gpt-5.2` | reasoning | rejects `reasoning_effort` **when tools are attached** |
| `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano` | reasoning | same tool restriction as `gpt-5.2` |
| `gpt-5.5` | reasoning | |
| `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` | reasoning | |
| `gpt-5.1-chat-latest`, `gpt-5.2-chat-latest`, `gpt-5.3-chat-latest` | chat | gpt-5 generation **chat** snapshots: `temperature` yes, `reasoning_effort` no |
| `chat-latest` | chat | auto-follows the latest `gpt-5.x-chat` snapshot |
| `gpt-oss-120b` | chat | open-weight model, non-reasoning |

**Reasoning-model rule:** reasoning models reject `temperature` and take `reasoning_effort`;
chat models are the reverse. The `*-chat-latest` aliases sit inside the gpt-5 generation but
are **chat** models — they read `verbosity` but not `reasoning_effort`. The families are
listed per model in `src/core/agents/llm_capabilities.py`, which both the API validator and
the runtime factory read; a prefix such as "starts with gpt-5" gets the aliases wrong.

### On the allowlist

The mode validator (`validate_mode_config` in `src/api/models/api_schemas/config/llm_config.py`) rejects
any `model` outside the table above with a `422`. When OpenAI ships a new model, add it to
`REASONING_MODELS` or `CHAT_MODELS` in `src/core/agents/llm_capabilities.py` — that split is
the allowlist (`OPENAI_CASCADE_MODELS`) *and* decides which knobs the model accepts — then to
the table above.

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
| `cartesia` | `cascade` only | `ink-whisper` (43 languages) or `ink-2` (English only) | `language` fixed ISO 639-1, no auto-detect, default `en` |
| `deepgram` | `cascade` only | `nova-3` (multilingual, 45 languages); also `nova-2`, `flux-general-en` (English), `flux-general-multi` | `language` BCP-47 or `multi` (auto-detect; omitted — `multi` on `nova-3` / `flux-general-multi`, `en-US` on the rest); `enable_diarization` (bool, default `false` — omitted stays **off**, never force-enabled); `keyterm` (string or list — omitted — not sent, no biasing); `api_key` falls back to system `DEEPGRAM_API_KEY` |
| `elevenlabs` | `cascade` only | `scribe_v2_realtime` (auto-detects ~190 languages); also `scribe_v2`, `scribe_v1` | `language_code` **ISO 639-3** (`eng`, `hin`) — omit to auto-detect; `no_verbatim` (bool, default `false` — omitted keeps fillers); `api_key` falls back to system `ELEVENLABS_API_KEY` — the same variable the ElevenLabs TTS provider uses |
| `openai` | `cascade` only (in `pipeline` it collapses to `native`) | `gpt-4o-mini-transcribe`; also `gpt-4o-transcribe`, `whisper-1` | `language` ISO 639-1 — omitting it turns on `detect_language` rather than pinning English; `detect_language` (bool, default `false`) turns on auto-detect and overrides `language`; `prompt` (whisper-1 only); `noise_reduction_type` (`near_field` / `far_field`); `use_realtime` (bool, default **`true`** — streams over the realtime transcription socket); `api_key` falls back to system `OPENAI_API_KEY` — the same variable the cascade LLM uses |
| `native` | `pipeline` only — rejected in `cascade` (no realtime model to self-transcribe) | n/a (the conversational LLM transcribes itself: `gpt-4o-mini-transcribe`) | no config |

Ignored entirely in `realtime` mode (the model always transcribes itself).

**Quirks worth knowing before you rely on them:**

- `assistant_stt_model="openai"` is a real cascade provider, but in **pipeline** mode it is rewritten
  to `"native"` at resolve time: the pipeline's realtime model already transcribes with the same
  vendor and the same `gpt-4o-mini-transcribe`, so a second connection would only cost money. (This
  also keeps pre-migration rows, where `"openai"` *meant* native, working unchanged.)
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
| `sarvam` | `language` | `unknown` | `unknown` = auto-detect, keeps code-switching with `codemix` | a BCP-47 Indic code (`hi-IN`) locks one fixed language; omitted stays auto-detect. The accepted set is **per model** — `saarika:v2.5` and `saaras:v2.5` take 11 codes, `saaras:v3` takes 23. A code outside the selected model's set is dropped back to `unknown` with a logged error |
| `sarvam` | `mode` | `codemix` on `saaras:v3`, otherwise the model's own default | transcription style (`codemix`, `transcribe`, `translate`, `verbatim`, `translit`) | **`saaras:v3` only.** On `saarika:v2.5` / `saaras:v2.5` the key is dropped before construction with a logged warning — see the pitfall below |
| `sarvam` | `api_key` | system `SARVAM_API_KEY` | auth for the STT call | per-assistant override wins; both missing → **pipeline** falls back to `native` (warning), **cascade** aborts |
| `cartesia` | `model` | `ink-whisper` (pinned in factory) | 43-language STT model | `ink-2` is English only; the factory pins the model explicitly so the plugin's own default flip can't bite |
| `cartesia` | `language` | `en` | exactly one fixed language — **no auto-detect** | ISO 639-1 only (`en`, `hi`) — a BCP-47 code like `en-US` is rejected and logged, and the default is used; omitted means `en` |
| `cartesia` | `api_key` | system `CARTESIA_API_KEY` | auth | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `deepgram` | `model` | `nova-3` | multilingual, 45 languages | `nova-2`, `flux-general-en` (English only), `flux-general-multi`; omitted keeps the default |
| `deepgram` | `language` | `multi` on `nova-3` / `flux-general-multi`, else `en-US` | `multi` = auto-detect; BCP-47 = fixed | BCP-47 (`en-US`, `hi-IN`) or `multi` — a 3-letter code like `hin` is rejected and logged; omitted auto-detects wherever the model can, which is billed at a higher rate |
| `deepgram` | `enable_diarization` | `false` | label each utterance with its speaker (nova models) | `true` turns it on; **omitted stays `false`, never force-enabled** |
| `deepgram` | `keyterm` | not sent | bias recognition toward a term | a string/list biases recognition (`nova-3`/`flux` only); **omitted — the key is not sent, no biasing** |
| `deepgram` | `api_key` | system `DEEPGRAM_API_KEY` | auth | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `elevenlabs` | `model` | `scribe_v2_realtime` | auto-detects ~190 languages | `scribe_v2`, `scribe_v1`; omitted keeps the default |
| `elevenlabs` | `language_code` | omitted → auto-detect (~190 languages) | **ISO 639-3** (`eng`, `hin`) pins one language | ISO 639-3 only — BCP-47 or ISO 639-1 closes the socket with `1008 invalid_request` upstream, so an unrecognized code is rejected and logged here and the call auto-detects instead |
| `elevenlabs` | `no_verbatim` | `false` | strip filler words from the transcript when `true` | `true` strips fillers; **omitted stays `false` — fillers kept** |
| `elevenlabs` | `api_key` | system `ELEVENLABS_API_KEY` | auth — one variable covers both the STT and TTS stages | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `openai` | `model` | `gpt-4o-mini-transcribe` | which OpenAI transcription model runs | `gpt-4o-transcribe` is more accurate and dearer; `whisper-1` is the legacy batch model (the only one that reads `prompt`). `gpt-realtime-whisper` is **rejected** — it has no server-side endpointing and needs a client-side VAD this runtime can't hand it |
| `openai` | `language` | omitted → `detect_language` turns on | one fixed ISO 639-1 language | ISO 639-1 only (`en`, `hi`) — `hi-IN` is rejected and logged; omitting it auto-detects rather than pinning English. Ignored when `detect_language` is `true` |
| `openai` | `detect_language` | `false` | auto-detect the spoken language | `true` blanks `language` and lets the model detect; omitted keeps the pinned language |
| `openai` | `prompt` | not sent | biases spellings/jargon (names, product terms) | a string biases recognition on **`whisper-1` only**; the gpt-4o transcribe models ignore it |
| `openai` | `noise_reduction_type` | not sent | server-side noise reduction | `near_field` (headset) or `far_field` (speakerphone / room mic); omitted sends none |
| `openai` | `use_realtime` | `true` | streams over OpenAI's realtime transcription WebSocket (interim results, low latency) | `false` switches to the batch REST API — cheaper, but adds a full utterance of latency per turn and gives no interim results. **This inverts the plugin's own default**, which is batch |
| `openai` | `api_key` | system `OPENAI_API_KEY` | auth — the same variable the cascade LLM stage uses | override wins; both missing → **cascade** aborts (in pipeline the provider is already collapsed to `native`) |

`native` (pipeline only) takes no config — the conversational LLM transcribes itself
(`gpt-4o-mini-transcribe`).

### STT pitfalls & what not to combine

These are the easy-to-miss traps. All statements match the plugin behaviour in LiveKit Agents.

- **Sarvam `language` and `mode` are gated per model, and the plugin *raises* rather than
  warning.** `mode` exists on `saaras:v3` alone; the language set on `saarika:v2.5` /
  `saaras:v2.5` is the 11-code subset. Passed straight through, either mismatch is a
  `ValueError` out of the STT constructor — which ends the job before the call connects,
  a harder failure than any wrong language code elsewhere on this page. Both are therefore
  validated first: a bad language falls back to `unknown` (auto-detect), an unsupported
  `mode` is dropped so the model uses its own default. Both are logged.
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
- **Four providers, four language-code standards. They are not interchangeable.** The same spoken
  language is written four different ways depending on which provider you selected, and a code from
  the wrong standard is rejected (logged, then the provider default applies) rather than sent:

  | Provider | Standard | English | Hindi |
  |---|---|---|---|
  | `sarvam` | BCP-47 Indic | `en-IN` | `hi-IN` |
  | `cartesia` | ISO 639-1 | `en` | `hi` |
  | `deepgram` | BCP-47 | `en-US` | `hi-IN` |
  | `elevenlabs` | **ISO 639-3** | `eng` | `hin` |
  | `openai` | ISO 639-1 | `en` | `hi` |

  ElevenLabs is the one that bites: it is the only ISO 639-3 surface here, and a BCP-47 code does not
  degrade gracefully upstream — Scribe closes the WebSocket with
  `1008 invalid_request: Invalid language code received: 'en-US'` on the first utterance, and the
  agent retries the same failure until the call ends.
- **`preferred_languages` is never a language parameter.** `assistant_interaction_config.preferred_languages`
  hints the *transcription prompt* on the `native` path. It is BCP-47, it is a list, and it is not
  sent to any speech provider as a `language`. Pin a language on `assistant_stt_config` or not at all.
- **Omitting the language means auto-detect, except on Cartesia.** `sarvam` → `unknown`;
  `elevenlabs` → no code sent (~190 languages); `openai` → `detect_language` on; `deepgram` →
  `multi` on `nova-3`/`flux-general-multi`, `en-US` on the models that cannot detect;
  `cartesia` → `en`, because Cartesia has no detection at all. Use Sarvam or Deepgram `multi` for a
  caller who switches language mid-sentence.
- **Pinning `language_code` (ElevenLabs) disables auto-detect.** `omit` → auto-detect; `set` → pinned & detection off. So a caller who switches languages mid-call is mis-transcribed once pinned. Set it only when a fixed language is guaranteed.
- **On flux, `language` becomes `language_hint` — and only `flux-general-multi` reads it.** The hint is
  sent as a list; `multi` is a nova-only sentinel and is never forwarded. A language set on
  `flux-general-en` is dropped with a warning.
- **One `ELEVENLABS_API_KEY` covers both stages,** STT and TTS. The per-assistant fields stay separate, though: `assistant_stt_config.api_key` and `assistant_tts_config.api_key` are scoped to whichever provider that stage selected, so on a mixed assistant they hold two different vendors' keys. Sending one vendor's key on another vendor's path fails auth (Sarvam answers `403`).
- **Missing key in cascade aborts (no fallback).** If neither a config `api_key` nor the system env var is present, `create_stt` returns `None` and the cascade job is abandoned (logged) — it does **not** silently switch models. In `pipeline` mode the same selection only degrades to `native` transcription with a warning.
- **OpenAI STT: `prompt` only works on `whisper-1`.** The `gpt-4o-transcribe` family accepts the
  field and ignores it — no error, no biasing. If you need prompt biasing, pick `whisper-1` (and
  accept that it is the slower, batch-only model).
- **OpenAI STT: `use_realtime: false` is a latency decision, not a cosmetic one.** Batch mode holds
  each utterance until it ends, then transcribes it in one HTTP call — no interim results, and the
  turn-taking pipeline waits. Only switch it off when cost beats responsiveness.
- **OpenAI STT: `detect_language` beats `language`.** Setting both is not an error — `language` is
  simply dropped. Pick one.
- **Multilingual billing.** Deepgram `language: "multi"` (and any multilingual detection) is billed at a higher per-minute rate than monolingual. Factor this in before enabling it broadly.

## TTS

`assistant_tts_model` + `assistant_tts_config`. The synthesis **model is hardcoded per provider
except ElevenLabs** (which now accepts a `model` key). Synthesis params are configurable via
`assistant_tts_config`.

| Provider | Model (default) | Required config | Configurable synthesis params |
|---|---|---|---|
| `cartesia` | `sonic-3` (fixed) | `voice_id` | `language` (default `en`), `speed` (float `0`–`3`, default `1.0`), `volume` (default `1.0`), `emotion`, `pronunciation_dict_id` |
| `sarvam` | `bulbul:v3` (fixed) | `speaker` — **v3 roster only**, see below | `target_language_code` (default `en-IN`), `pace` (`0.3`–`3.0`, default `1.0`), `speech_sample_rate` (one of `8000`/`16000`/`22050`/`24000`/`32000`/`44100`/`48000`, default `24000`), `temperature` (`0.01`–`2.0`, default `0.3`) |
| `elevenlabs` | `eleven_v3` (default) | `voice_id` | `model` (`eleven_v3`, `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`), `voice_settings` (`stability`, `similarity_boost`, `style`, `speed` — **not on v3**, `use_speaker_boost`); non-streaming (HTTP chunked) |
| `mistral` | `voxtral-mini-tts-2603` (fixed) | `voice_id` | `response_format="opus"`, non-streaming |

All four accept an optional `api_key`, falling back to the matching system key
(`CARTESIA_API_KEY` / `SARVAM_API_KEY` / `ELEVENLABS_API_KEY` / `MISTRAL_API_KEY`).

Speed is therefore **configurable per assistant** for Cartesia, Sarvam and ElevenLabs (the three
providers whose SDK exposes a rate knob). See each tab in [create](../api/assistant/create.md) for
valid ranges.

**ElevenLabs `speed` does not apply to `eleven_v3`**, which is the default model here — v3 has no
speed control at all
([ElevenLabs docs](https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech)). A `speed`
stored against v3 is dropped before the call with a log line naming the models that do support it
(`eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`); the rest of `voice_settings`
is sent unchanged. On v3, `stability` also behaves as three modes — creative (`0.0`), natural
(`0.5`), robust (`1.0`) — rather than a continuum.

**Sarvam `target_language_code` defaults to `en-IN`, and accepts 11 codes only.** Bulbul speaks
`bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN` —
note `en-IN`, **not** `en-US`, which reads like a reasonable value and is not one. Anything outside
the list is logged and replaced with `en-IN` rather than failing every synthesis. Omitting it stores
`null`, and the factory substitutes `en-IN`. (Earlier builds defaulted the schema to `bn-IN`, which silently overrode the
factory fallback and synthesized Bengali for every assistant that left the field out. Assistants
created before this fix have `bn-IN` written into their stored config — send the field explicitly to
correct them.)

**Cartesia's model is fixed at `sonic-3`** and has no config field. It is the newest ID the
installed plugin knows; `sonic-3.5` is a [LiveKit Inference](https://docs.livekit.io/agents/models/inference.md)
gateway model, and Inference needs LiveKit Cloud credentials this deployment does not use. The
`emotion` and `pronunciation_dict_id` params are sonic-3-only, and `speed` must be numeric there
(the `"slow"`/`"fast"` presets belong to the older models and are rejected by the plugin), so making
the model configurable means gating those three per model.

**Sarvam `speaker` must come from the bulbul:v3 roster.** The two Bulbul generations share no
speaker at all, so every v2 name — `anushka`, `manisha`, `vidya`, `arya`, `abhilash`, `karun`,
`hitesh` — is invalid on the v3 model this platform pins. The v3 speakers are:

`aayan`, `aditya`, `advait`, `amelia`, `amit`, `ashutosh`, `dev`, `ishita`, `kabir`, `kavitha`,
`kavya`, `manan`, `neha`, `pooja`, `priya`, `rahul`, `ratan`, `ritu`, `rohan`, `roopa`, `rupali`,
`shreya`, `shruti`, `shubh`, `simran`, `sophia`, `suhani`, `sumit`, `tanya`, `varun`.

Unlike a bad language code, a bad speaker is **not** substituted: the call ends before it starts,
with one log line naming the valid speakers. Substituting would answer the call in a voice nobody
chose. (Before this check the Sarvam plugin's own `ValueError` escaped the factory and killed the
job with a traceback instead.)

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
