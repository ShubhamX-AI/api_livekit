# Models & Providers

Single reference for every model, provider, and config default the runtime actually uses. If this page and another doc disagree, this page is correct; file an issue against
the other one.

`assistant_mode` selects the *shape* of the session (`pipeline`, `realtime`, `cascade`, `duplex`) — see
[Assistant modes](../concepts/assistant-modes.md). This page covers what each stage of each mode can
actually be configured to run.

## Realtime LLM (`pipeline` and `realtime` modes)

Both modes route through a realtime model — `pipeline` uses it in text-only mode with an external TTS,
`realtime` lets it speak its own audio. Configured via `assistant_llm_config`.

| Field | Values | Default |
|---|---|---|
| `provider` | `openai` in `pipeline` mode (`gemini` is rejected — see [Compatibility Matrix](compatibility.md#mode-llm-provider)); `gemini` or `openai` in `realtime` mode | `gemini` in `realtime` mode, `openai` in `pipeline` mode |
| `model` | **Both validated.** OpenAI: one of the [realtime models](#openai-realtime-models). Gemini: `gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.1-flash-live-preview` or `gemini-2.5-flash-native-audio-preview-12-2025` (the plugin also lists `gemini-live-2.5-flash-native-audio`, which is Vertex-only and rejected). The Live API is a much smaller set than the Gemini chat models, and a chat id such as `gemini-2.5-flash` opens a socket the API then closes | `gemini-3.8-live` (gemini), `gpt-realtime-1.5` (openai) |
| `voice` | Validated per vendor: the 30-name Gemini Live roster for `gemini`; for `openai`, anything that is not a Gemini name | `Puck` (gemini), `marin` (openai). **Honored only in `realtime` mode** — `pipeline` mode emits text, so voice is meaningless there and the field is silently ignored. |
| `api_key` | string | falls back to system `GOOGLE_API_KEY` / `OPENAI_API_KEY` |

### Voices

**OpenAI realtime** (`realtime` mode): `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`,
`verse`, `marin` (default) and `cedar`. OpenAI recommends `marin` or `cedar` for the best quality
([voice options](https://developers.openai.com/docs/guides/realtime-conversations#voice-options),
checked 2026-10-17). The API does not keep its own list here — OpenAI ships new voices without an
SDK release — so it accepts any name that is not a Gemini voice. Check a new name against
OpenAI's list before using it.

**Gemini Live** (`realtime` mode, all 30, checked against the plugin): `Achernar`, `Achird`,
`Algenib`, `Algieba`, `Alnilam`, `Aoede`, `Autonoe`, `Callirrhoe`, `Charon`, `Despina`,
`Enceladus`, `Erinome`, `Fenrir`, `Gacrux`, `Iapetus`, `Kore`, `Laomedeia`, `Leda`, `Orus`,
`Puck` (default), `Pulcherrima`, `Rasalgethi`, `Sadachbia`, `Sadaltager`, `Schedar`, `Sulafat`,
`Umbriel`, `Vindemiatrix`, `Zephyr`, `Zubenelgenubi`.

**GPT-Live** (`duplex` mode): see [GPT-Live](#gpt-live-duplex-mode-only). **TTS voices** for
`pipeline` and `cascade` are set in `assistant_tts_config`: a Sarvam `speaker` from the rosters in
[TTS](#tts), or a `voice_id` from the Cartesia, ElevenLabs or Mistral voice library.

### OpenAI realtime models

The OpenAI realtime models accepted are `gpt-realtime`, `gpt-realtime-1.5`
(default), `gpt-realtime-2`, `gpt-realtime-2.1`, `gpt-realtime-2.1-mini`, `gpt-realtime-2025-08-28`
and `gpt-realtime-mini`. The two `2.1` models were added on 2026-10-17 after a live session probe
with this platform's exact session shape, in both audio (realtime) and text (pipeline) output.

OpenAI realtime additionally runs fixed turn-taking params not exposed to the API: `TurnDetection(type="semantic_vad", eagerness="high", create_response=True, interrupt_response=False)`, and
`RealtimeTruncationRetentionRatio(retention_ratio=0.75, post_instructions=8000)`.

The truncation half is **sent only to the `gpt-realtime*` line**. `session.truncation` is a GA
Realtime API field that `gpt-4o-realtime-preview` and `gpt-4o-mini-realtime-preview` do not have,
and the API errors on an unknown session field instead of ignoring it. Those two are also no
longer accepted at all — probed on 2026-08-13, the account does not serve either — but a stored
row can still hold one, so the rule remains. See
[Assistant modes → LLM context truncation](../concepts/assistant-modes.md#llm-context-truncation).

!!! note "Which Gemini Live model to pick"
    The default is **`gemini-3.8-live`** — the stable low-latency line Google names for voice
    agents, and the one every platform feature works on (greeting, max-duration farewell,
    silence re-prompts, agent handoff).

    **`gemini-3.8-live-extended-thinking`** reasons before it speaks. It is the choice for
    complex multi-step agents and it trades first-token latency for that; its function calling
    is asynchronous only, which is how it masks tool latency. Nothing rejects it — expect a
    slower first word.

    **`gemini-3.1-flash-live-preview`** is still selectable. Its mid-session limitation (a 1007
    close on `send_client_content` after the first model turn, which silently dropped the
    farewell and re-prompts) was a **plugin** bug, fixed in `livekit-plugins-google` 1.8.2 —
    the version this platform pins. On older deployments the symptom is back; see
    [Troubleshooting](troubleshooting.md#gemini-live-mid-session-updates).

    **`gemini-live-2.5-flash-native-audio`** is the Vertex AI id and is **rejected with a
    `422`**. The plugin lists it, but raises
    `ValueError: … is a VertexAI model, but vertexai=False` while building the model,
    and this deployment authenticates with `GOOGLE_API_KEY`. Accepted, it would be a call that
    connects and then loses its worker before the first word.

### Gemini Live pricing

All rates, for every provider, are on [Pricing](pricing.md). Google's public list price, paid tier, per 1M tokens
([pricing](https://ai.google.dev/gemini-api/docs/pricing), checked 2026-09-22). Estimated
per-call cost uses these numbers — see the `estimated_cost_usd` field on the usage record.

| Model | Input text | Input audio | Input image/video | Output text | Output audio |
|---|---|---|---|---|---|
| `gemini-3.8-live` | $0.75 | $3.00 (≈$0.005/min) | $1.00 (≈$0.002/min) | $4.50 | $12.00 (≈$0.018/min) |
| `gemini-3.8-live-extended-thinking` | $0.75 | $3.00 | $1.00 | $4.50 | $12.00 |
| `gemini-3.1-flash-live-preview` | $0.75 | $3.00 | $1.00 | $4.50 | $12.00 |
| `gemini-2.5-flash-native-audio-preview-12-2025` | $0.50 | $3.00 | $3.00 | $2.00 | $12.00 |

Thinking tokens bill as output text, so extended-thinking costs more per turn than its row
suggests. Search grounding is billed separately by Google: 5,000 free requests per month
shared across Gemini 3.x models, then $14 per 1,000 requests.

Native user-transcription (`assistant_stt_model="native"`, pipeline mode only) uses OpenAI
`gpt-4o-mini-transcribe` regardless of which realtime provider is selected.

In `realtime` mode both vendors transcribe the caller: OpenAI is given
`gpt-4o-mini-transcribe` explicitly, and Gemini transcribes with its own model because the
Google plugin enables `input_audio_transcription` whenever the argument is omitted. Neither
needs `assistant_stt_model` — that field is ignored in this mode.

## GPT-Live (`duplex` mode only)

OpenAI's full-duplex voice model, run as LiveKit's `openai.realtime.GPTLiveModel` with this deployment's own `OPENAI_API_KEY`. It listens while it
speaks and decides its own turns. A second model — the **backend**, an ordinary Responses model —
does the reasoning and runs the tools. Configured via `assistant_llm_config`. How a call runs:
[Duplex Mode](../concepts/duplex.md).

| Field | Values | Default |
|---|---|---|
| `provider` | `openai` only | `openai` |
| `model` | `gpt-live-1` | `gpt-live-1` |
| `voice` | `beacon`, `cedar`, `cinder`, `marin`, `stone`, `vesper` (`aster` was removed in livekit-agents 1.8.8) | `marin` |
| `backend_model` | any reasoning model from the [cascade table](#documented-models) | `gpt-5.6-luna` |
| `backend_instructions` | string, up to 4000 characters | a short built-in instruction: use the tools when needed, answer briefly |
| `reasoning_effort`, `verbosity`, `service_tier`, `tool_choice`, `parallel_tool_calls`, `max_output_tokens` | as in [cascade](#cascade-llm-cascade-mode-only), checked against `backend_model` | unset |
| `temperature` | rejected — every backend model is a reasoning model | — |
| `api_key` | string | falls back to system `OPENAI_API_KEY` |

The **voice persona** is `assistant_prompt`; `backend_instructions` is a separate set for the
backend. GPT-Live fixes both, and the voice, for the whole session. OpenAI's
[Prompting GPT-Live](https://developers.openai.com/api/docs/guides/live-prompting) guide explains
how to split a prompt between the two.

Duplex ignores `assistant_tts_*` and `assistant_stt_*`. It refuses, with a `422` at create or a
`400` at update, three things GPT-Live cannot do: a prerecorded greeting
(`assistant_greeting_audio`), filler words, and `text_only` web calls. See
[Compatibility Matrix → Duplex mode](compatibility.md#duplex-mode).

**Pricing.** GPT-Live is billed per second of open session, at $0.05 per minute
([OpenAI pricing](https://developers.openai.com/api/docs/pricing), checked 2026-10-17). The backend's
tokens are billed separately at that model's own rate. The usage record carries both: the voice
model's seconds in `llm_session_duration`, and the backend's tokens as their own `model_usage` entry.

## Cascade LLM (`cascade` mode only)

Runs as LiveKit's `openai.responses.LLM` (the OpenAI Responses API) — cheaper than
chat-completions, same `@function_tool` contract. Configured via `assistant_llm_config`.

| Field | Values | Default |
|---|---|---|
| `provider` | `openai` only — any other value is rejected | `openai` |
| `model` | one of the documented model IDs below — **validated against the allowlist at creation/update time** | `gpt-4.1` |
| `api_key` | string | falls back to system `OPENAI_API_KEY` |
| `temperature` | `0.0`–`2.0` — **chat models only** | SDK default (`0.8`) |
| `max_output_tokens` | int, at least 16 | unset (model default) |
| `reasoning_effort` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` — **reasoning models only** | unset |
| `service_tier` | `auto`, `default`, `fast`, `priority` — all models. `flex` — **gpt-5 generation only**. `scale` is not an OpenAI tier and is rejected. [Measured table](compatibility.md#service_tier-measured) | unset (recommended) |
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
| `gpt-5.2` | reasoning | rejects `reasoning_effort` **when tools are attached** |
| `gpt-5.4`, `gpt-5.4-mini` | reasoning | same tool restriction as `gpt-5.2` |
| `gpt-5.5` | reasoning | |
| `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` | reasoning | |
| `gpt-6-luna`, `gpt-6-sol` | reasoning | added 2026-10-17; accept `reasoning_effort` `none`/`low`/`medium`/`high`/`xhigh` (not `minimal`) with tools, `verbosity` and `flex`; reject `temperature` |

**`gpt-5.1`** and **`gpt-5.4-nano`** were removed from the allowlist in 1.6.0; OpenAI retires both on
**2027-04-01**. `uv run python scripts/migrate_retired_models.py --apply` moves stored assistants to
the replacements LiveKit names: `gpt-5.1` to `gpt-6-sol`, `gpt-5.4-nano` to `gpt-6-luna`.

**Reasoning-model rule:** reasoning models reject `temperature` and take `reasoning_effort`;
chat models are the reverse. Each model's family is listed explicitly, and the same list decides
what the API accepts and what the call sends. Membership is spelled out, never matched by prefix: `gpt-5.2-chat-latest` started with
"gpt-5" and was a chat model, and a prefix test sent it `reasoning.effort` anyway.

!!! danger "Removed from the allowlist: the `*-chat-latest` aliases and `gpt-oss-120b`"

    `gpt-5.1-chat-latest`, `gpt-5.2-chat-latest` and `gpt-5.3-chat-latest` were **retired by
    OpenAI on 2026-06-19**. Probed on 2026-08-13 they answer `404 Model not found` — even though
    `GET /v1/models` still *lists* them, which is why the listing alone is never evidence.
    `gpt-oss-120b` is served by baseten and groq, not by `api.openai.com`.

    An assistant still holding one of these answers calls with **silence**: OpenAI rejects
    every LLM turn on the model id alone. Find them with
    `uv run python scripts/audit_assistant_models.py`, and see
    [Troubleshooting → The silent call](troubleshooting.md).

!!! note "`chat-latest` works, and is still not allowlisted"
    Probed on 2026-08-13, `chat-latest` answers HTTP 200 on the direct API — it is a real model,
    not a gateway-only id. It is left off the allowlist because it fits **neither** family and
    would need its own: it *rejects* `temperature` like a reasoning model, and accepts
    `reasoning_effort` and `verbosity` with the single value `medium` (anything else is a `400`).
    No assistant currently uses it. If you want it, it can be added with those constraints
    encoded — the knob-value half is already caught by the config probe.

### On the allowlist

Two gates, in order.

**The static allowlist.** Create and update reject any `model` outside the table above with a
`422`. A model is added to the platform only after it has been checked against OpenAI, together
with the family that decides which knobs it accepts.

**The live check.** No static list can know that OpenAI retired something last week, which is
exactly how the aliases above became a live outage. So create and update also ask OpenAI
whether the account still serves the model (`GET /v1/models`, cached for up to an hour) and answer `422`/`400` if not. If OpenAI cannot be
reached the write is **allowed** — an OpenAI outage must not make assistants un-editable.

The pipeline and realtime modes have their own, separate allowlist of
OpenAI **realtime** model IDs — the two sets do not overlap, and sending a chat model such as
`gpt-4.1` in pipeline mode is a `422`. Gemini Live IDs have their own list
and are validated too. Full table:
[Compatibility Matrix → Model IDs](compatibility.md#model-ids).

## STT

`assistant_stt_model` + `assistant_stt_config`. Pipeline mode (a parallel transcription tap beside the
realtime model) and cascade mode (STT as the session's first stage) read the same fields but do not
always treat them the same way — see the quirks below.

!!! note "`model` is allowlisted per provider"
    The `model` field in every STT and TTS config is checked against that provider's real model
    set, and a value outside it is a `422`:

    ```json
    { "detail": "'deepgram' does not have a STT model called 'nova-9' — choose one of: flux-general-en, flux-general-multi, nova-3, nova-3-general, nova-3-multilingual. See docs/reference/models.md." }
    ```

    These fields used to accept any string under 40 characters, so a typo was stored happily and
    then ended the job at call start — the STT stage could not be built, the session never started,
    and the caller heard nothing. The sets are kept in step with the LiveKit plugins this platform
    runs. A provider whose model is **pinned** by the platform (Cartesia TTS, Mistral) takes no
    `model` field at all.

| Provider | Valid in | Model default | Other config |
|---|---|---|---|
| `sarvam` | `pipeline` (default), `cascade` | `saaras:v3` (also `saaras:v4`) | `language` default `unknown` (auto-detect); `mode` default `codemix` (also `transcribe`, `translate`, `verbatim`, `translit`; honoured in both pipeline and cascade) |
| `cartesia` | `cascade` only | `ink-whisper` (43 languages) or `ink-2` (English only) | `language` fixed ISO 639-1, no auto-detect, default `en` |
| `deepgram` | `cascade` only | `nova-3` (multilingual, 45 languages); also `nova-3-general`, `nova-3-multilingual`, `flux-general-en` (English), `flux-general-multi` | `language` BCP-47 or `multi` (auto-detect; omitted — `multi` on `nova-3` / `flux-general-multi`, `en-US` on the rest); `enable_diarization` (bool, default `false` — omitted stays **off**, never force-enabled); `keyterm` (string or list — omitted — not sent, no biasing); `api_key` falls back to system `DEEPGRAM_API_KEY` |
| `elevenlabs` | `cascade` only | `scribe_v2_realtime` (auto-detects ~190 languages); also `scribe_v2`, `scribe_v1` | `language_code` **ISO 639-3** (`eng`, `hin`) — omit to auto-detect; `no_verbatim` (bool, default `false` — omitted keeps fillers); `api_key` falls back to system `ELEVENLABS_API_KEY` — the same variable the ElevenLabs TTS provider uses |
| `openai` | `cascade` only (in `pipeline` it collapses to `native`) | `gpt-4o-mini-transcribe`; also `gpt-4o-transcribe`, `whisper-1` | `language` ISO 639-1 — omitting it turns on `detect_language` rather than pinning English; `detect_language` (bool, default `false`) turns on auto-detect and overrides `language`; `prompt` (whisper-1 only); `noise_reduction_type` (`near_field` / `far_field`); `use_realtime` (bool, default **`true`** — streams over the realtime transcription socket; `false` is accepted only with `whisper-1`); `api_key` falls back to system `OPENAI_API_KEY` — the same variable the cascade LLM uses |
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
the env var; if **both** are missing, a cascade assistant aborts (the STT stage
is not built and the worker logs it — it does **not** silently fall back), while pipeline selection of a cascade-only
provider (cartesia / deepgram / elevenlabs) degrades to native transcription with a warning.

| Provider | Channel (config key) | Default | Meaning | What changes if you change it |
|---|---|---|---|---|
| `sarvam` | `model` | `saaras:v3` | which Saras model transcribes | `saaras:v4` swaps the model; omitted keeps the default. The `saaras:v2.5` / `saarika:v2.5` pair was sunset by Sarvam and is rejected with a `422` |
| `sarvam` | `language` | `unknown` | `unknown` = auto-detect, keeps code-switching with `codemix` | a BCP-47 Indic code (`hi-IN`) locks one fixed language; omitted stays auto-detect. The accepted set is **per model** (both current models take the same 23 codes, but the roster has diverged before). A code outside the selected model's set is dropped back to `unknown` with a logged error |
| `sarvam` | `mode` | `codemix` | transcription style (`codemix`, `transcribe`, `translate`, `verbatim`, `translit`) | both current models accept it; on a model that does not, the key is dropped before construction with a logged warning — see the pitfall below |
| `sarvam` | `api_key` | system `SARVAM_API_KEY` | auth for the STT call | per-assistant override wins; both missing → **pipeline** falls back to `native` (warning), **cascade** aborts |
| `cartesia` | `model` | `ink-whisper` (pinned in factory) | 43-language STT model | `ink-2` is English only; the factory pins the model explicitly so the plugin's own default flip can't bite |
| `cartesia` | `language` | `en` | exactly one fixed language — **no auto-detect** | ISO 639-1 only (`en`, `hi`) — a BCP-47 code like `en-US` is rejected and logged, and the default is used; omitted means `en` |
| `cartesia` | `api_key` | system `CARTESIA_API_KEY` | auth | override wins; both missing → **pipeline** degrades to `native` (warning), **cascade** aborts |
| `deepgram` | `model` | `nova-3` | multilingual, 45 languages | `nova-3-general`, `nova-3-multilingual`, `flux-general-en` (English only), `flux-general-multi`; omitted keeps the default |
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
| `openai` | `use_realtime` | `true` | streams over OpenAI's realtime transcription WebSocket (interim results, low latency) | `false` switches to the batch REST API — cheaper, but adds a full utterance of latency per turn, gives no interim results, and is **rejected for every model except `whisper-1`** because that path reports no token usage. **This inverts the plugin's own default**, which is batch |
| `openai` | `api_key` | system `OPENAI_API_KEY` | auth — the same variable the cascade LLM stage uses | override wins; both missing → **cascade** aborts (in pipeline the provider is already collapsed to `native`) |

`native` (pipeline only) takes no config — the conversational LLM transcribes itself
(`gpt-4o-mini-transcribe`).

### STT pitfalls & what not to combine

These are the easy-to-miss traps. All statements match the plugin behaviour in LiveKit Agents.

- **Sarvam `language` and `mode` are gated per model, and the plugin *raises* rather than
  warning.** `saaras:v3` and `saaras:v4` currently accept the same languages and modes, but
  the roster has diverged before: the sunset `saarika:v2.5` took no `mode` at all and spoke
  an 11-code subset of what `saaras:v3` speaks. Passed straight through, either mismatch is a
  `ValueError` out of the STT constructor — which ends the job before the call connects,
  a harder failure than any wrong language code elsewhere on this page. Both are therefore
  validated first: a bad language falls back to `unknown` (auto-detect), an unsupported
  `mode` is dropped so the model uses its own default. Both are logged.
- **The Deepgram allowlist is the priced set, not the whole plugin.** Only the `nova-3` line and
  the two `flux` models are accepted. Deepgram stopped publishing a price for the `nova-2`,
  `enhanced`, `base` and hosted-`whisper` tiers, and this platform prices every call it accepts,
  so those ids are a `422`. Accepted: `nova-3`, `nova-3-general`, `nova-3-multilingual`,
  `flux-general-en`, `flux-general-multi`.
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
- **Missing key in cascade aborts (no fallback).** If neither a config `api_key` nor the system env var is present, the STT stage is not built and the cascade job is abandoned (logged) — it does **not** silently switch models. In `pipeline` mode the same selection only degrades to `native` transcription with a warning.
- **OpenAI STT: `prompt` only works on `whisper-1`.** The `gpt-4o-transcribe` family accepts the
  field and ignores it — no error, no biasing. If you need prompt biasing, pick `whisper-1` (and
  accept that it is the slower, batch-only model).
- **OpenAI STT: `use_realtime: false` is accepted only for `whisper-1`.** Batch mode holds each
  utterance until it ends, then transcribes it in one HTTP call — no interim results, the
  turn-taking pipeline waits, and the response carries no usage at all. The other OpenAI STT
  models are billed per token, so batch mode would store zero STT spend for the call; that
  pairing is a 422. `whisper-1` is billed by audio duration, which the batch path measures
  locally, so it is the one model that may use it.
- **OpenAI STT: `detect_language` beats `language`.** Setting both is not an error — `language` is
  simply dropped. Pick one.
- **Multilingual billing.** Deepgram `language: "multi"` (and any multilingual detection) is billed at a higher per-minute rate than monolingual. Factor this in before enabling it broadly.

## TTS

`assistant_tts_model` + `assistant_tts_config`. The synthesis **model is hardcoded per provider
except ElevenLabs and Sarvam** (both accept a `model` key). Synthesis params are configurable via
`assistant_tts_config`.

| Provider | Model (default) | Required config | Configurable synthesis params |
|---|---|---|---|
| `cartesia` | `sonic-3` (fixed) | `voice_id` | `language` (default `en`), `speed` (float `0`–`3`, default `1.0`), `volume` (default `1.0`), `emotion`, `pronunciation_dict_id` |
| `sarvam` | `bulbul:v3` (default) | `speaker` — **from the chosen model's roster**, see below | `model` (`bulbul:v3`, `bulbul:v4-flash`), `target_language_code` (default `en-IN`), `pace` (`0.3`–`3.0`; `0.5`–`2.0` on v4-flash; default `1.0`), `speech_sample_rate` (one of `8000`/`16000`/`22050`/`24000`/`32000`/`44100`/`48000`; v4-flash takes only the first four; default `24000`), `temperature` (`0.01`–`2.0`, default `0.3`; **`bulbul:v3` only** — rejected on v4-flash, where Sarvam fixes it at `0.6`) |
| `elevenlabs` | `eleven_v3` (default) | `voice_id` | `model` (`eleven_v3`, `eleven_v3_conversational`, `eleven_v4`, `eleven_v4_turbo`, `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`), `voice_settings` (`stability`, `similarity_boost`, `style`, `speed`, `use_speaker_boost` — **most models read only some of them**, see below); non-streaming (HTTP chunked) |
| `mistral` | `voxtral-mini-tts-2603` (fixed) | `voice_id` | `response_format="opus"`, non-streaming |

All four accept an optional `api_key`, falling back to the matching system key
(`CARTESIA_API_KEY` / `SARVAM_API_KEY` / `ELEVENLABS_API_KEY` / `MISTRAL_API_KEY`).

Speed is therefore **configurable per assistant** for Cartesia, Sarvam and ElevenLabs (the three
providers whose SDK exposes a rate knob). See each tab in [create](../api/assistant/create.md) for
valid ranges.

**ElevenLabs `voice_settings` depend on the model.** Only `eleven_multilingual_v2` reads all five,
and the default, `eleven_v3`, reads only `stability`. What each one reads, checked 2026-10-17:
`style` and `use_speaker_boost` from the `can_use_style` / `can_use_speaker_boost` flags ElevenLabs'
own `GET /v1/models` reports per model; `speed` and `similarity_boost` from its model notes
([text-to-speech guide](https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech)),
since `/v1/models` has no flag for them.

| Model | `stability` | `similarity_boost` | `style` | `speed` | `use_speaker_boost` |
|---|---|---|---|---|---|
| `eleven_v3` (default) | yes | **no** | **no** | **no** | **no** |
| `eleven_v3_conversational` | yes | **no** | **no** | **no** | yes |
| `eleven_v4`, `eleven_v4_turbo` | yes | yes | **no** | **no** | **no** |
| `eleven_turbo_v2_5`, `eleven_flash_v2_5` (and the `_v2` versions) | yes | yes | **no** | yes | **no** |
| `eleven_multilingual_v2` | yes | yes | yes | yes | yes |

A setting marked **no** is **rejected with a `422`** at create and update, naming the setting and the
models that do read it. ElevenLabs itself accepts and ignores it (a live request on 2026-10-17
showed v4 taking `speed` and doing nothing with it), so a stored value would look like it was
shaping the voice. An assistant saved before 1.6.0 can still hold one: the worker drops it before
the request with one warning, and `uv run python scripts/migrate_tts_settings.py --apply` removes
it from the row. On v3, `stability` behaves as three modes, creative (`0.0`), natural (`0.5`) and
robust (`1.0`), rather than a continuum.

`eleven_monolingual_v1` and `eleven_multilingual_v1` are **rejected**: ElevenLabs retired them, and
every synthesis answers `400 unsupported_model`. The migration script moves stored rows to
`eleven_multilingual_v2`.

```json title="Valid — eleven_v3, the one setting that model reads"
{
  "assistant_tts_model": "elevenlabs",
  "assistant_tts_config": {
    "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
    "model": "eleven_v3",
    "voice_settings": { "stability": 0.5 }
  }
}
```

```text title="What a setting the model ignores looks like at the API (422)"
eleven_v3 does not read voice_settings speed. Remove it, or pick a model that reads it
(speed: eleven_flash_v2, eleven_flash_v2_5, eleven_multilingual_v2, eleven_turbo_v2,
eleven_turbo_v2_5). See docs/reference/models.md.
```

**Sarvam `target_language_code` defaults to `en-IN`.** Every Bulbul model speaks these 11 codes:
`bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN`, `te-IN` —
note `en-IN`, **not** `en-US`, which reads like a reasonable value and is not one. `bulbul:v4-flash`
also speaks 12 more Indic languages (the IN22 set: `as-IN`, `brx-IN`, `doi-IN`, `kok-IN`, `ks-IN`,
`mai-IN`, `mni-IN`, `ne-IN`, `sa-IN`, `sat-IN`, `sd-IN`, `ur-IN`), but only on a Sarvam subscription
that has them enabled; on `bulbul:v3` an IN22 code is a `422` (a row stored before 1.6.0 is logged and
replaced with `en-IN`). Anything outside
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

**Sarvam `speaker` must come from the chosen model's roster.** No two Bulbul generations share a
speaker, so every v2 name — `anushka`, `manisha`, `vidya`, `arya`, `abhilash`, `karun`, `hitesh` —
is invalid on v3, and no v3 name is valid on v4-flash. The API checks the speaker against the model
and answers `422`, naming the v4-flash voices built on the same name when there are any. The v3
speakers are:

`aayan`, `aditya`, `advait`, `amelia`, `amit`, `ashutosh`, `dev`, `ishita`, `kabir`, `kavitha`,
`kavya`, `manan`, `neha`, `pooja`, `priya`, `rahul`, `ratan`, `ritu`, `rohan`, `roopa`, `rupali`,
`shreya`, `shruti`, `shubh`, `simran`, `sophia`, `suhani`, `sumit`, `tanya`, `varun`.

The `bulbul:v4-flash` speakers carry their language and style in the name
(`<voice>_<language>_<style>`). All 224:

| Language tag | Speakers |
|---|---|
| `as` — Assamese (2) | `kangkana_as_conversational`, `mouchumi_as_conversational` |
| `bn` — Bengali (3) | `bappa_bn_conversation`, `bimal_bn_suspense`, `roopa_bn_conversational` |
| `en` — English (62) | `aditi_en_stories`, `amelia_en_conversational`, `aparna_en_companion`, `aparna_en_edtech`, `ashwin_en_sports`, `ashwin_en_sports_energetic`, `chandrika_en_stories`, `dev_en_conversational`, `dev_en_recovery`, `deven_en_conversation`, `girish_en_devotional`, `girish_en_documentary`, `ishita_en_customer`, `ishita_en_medical`, `ishita_en_numbers`, `ishita_en_social`, `ishita_en_stories`, `kalpit_en_edtech`, `nachiket_en_ads`, `neha_en_customer`, `neha_en_latenight`, `nupur_en_kids`, `ojas_en_social`, `payal_en_edtech`, `ritu_en_edtech`, `ritu_en_latenight`, `ritu_en_medical`, `ritu_en_reels`, `rohan_en_recovery`, `roopa_en_conversational`, `rustom_en_suspense`, `sanchita_en_companion`, `sanchita_en_insurance`, `sanchita_en_market`, `sanchita_en_recovery`, `sanchita_en_social`, `sarang_en_narration`, `shabana_en_edtech`, `shalini_en_companion`, `shalini_en_customer`, `shubh_en_ads`, `shubh_en_audiobook`, `shubh_en_narration`, `shubh_en_narration_gentle`, `shubh_en_numbers`, `shubh_en_recovery`, `shubh_en_sports`, `simran_en_ads`, `simran_en_automobile`, `simran_en_conversation`, `simran_en_customer`, `simran_en_edtech`, `simran_en_edtech_bot`, `simran_en_narration`, `simran_en_recovery`, `simran_en_sales`, `simran_en_therapist`, `sophia_en_conversational`, `sunny_en_social`, `varun_en_ads`, `varun_en_suspense`, `zarina_en_conversation` |
| `enhi` — English + Hindi (code-mixed) (13) | `ishita_enhi_companion`, `ishita_enhi_customer`, `ishita_enhi_customer_expressive`, `sanchita_enhi_companion`, `shalini_enhi_companion`, `shalini_enhi_customer`, `shubh_enhi_ads`, `shubh_enhi_banking`, `shubh_enhi_companion`, `simran_enhi_banking_expressive`, `simran_enhi_companion`, `simran_enhi_customer`, `sunny_enhi_customer` |
| `gu` — Gujarati (3) | `bhavik_gu_conversation`, `pooja_gu_conversational`, `pooja_gu_customer` |
| `hi` — Hindi (116) | `aarti_hi_customer`, `aayan_hi_conversational`, `aditya_hi_conversational`, `aditya_hi_sales`, `advait_hi_character`, `amit_hi_conversational`, `anand_hi_documentary`, `anand_hi_news`, `aparna_hi_customer`, `aparna_hi_kyc`, `aryaman_hi_ads`, `ashok_hi_character`, `ashok_hi_news`, `ashutosh_hi_conversational`, `chaitra_hi_customer`, `chhavi_hi_kids`, `chirag_hi_social`, `girish_hi_devotional`, `ishita_hi_ads`, `ishita_hi_ads_informal`, `ishita_hi_banking`, `ishita_hi_devotional`, `ishita_hi_edtech`, `ishita_hi_numbers`, `ishita_hi_social`, `kabir_hi_conversational`, `kavya_hi_conversational`, `kunal_hi_kids`, `mahesh_hi_documentary`, `manan_hi_conversational`, `mani_hi_conversational`, `mani_hi_devotional`, `mohit_hi_conversational`, `mukul_hi_ads`, `mukul_hi_suspense`, `nachiket_hi_devotional`, `priya_hi_recovery`, `rahul_hi_conversational`, `ratan_hi_customer_expressive`, `ratan_hi_devotional`, `ratan_hi_documentary`, `ratan_hi_latenight`, `ratan_hi_latenight_warm`, `ratan_hi_recovery`, `ratan_hi_social`, `ratan_hi_sports`, `rehan_hi_social`, `ritu_hi_ads_formal`, `ritu_hi_ads_informal`, `ritu_hi_banking`, `ritu_hi_conversation`, `ritu_hi_customer`, `ritu_hi_customer_utility`, `ritu_hi_customer_warm`, `ritu_hi_edtech`, `ritu_hi_edtech_bot`, `ritu_hi_insurance`, `ritu_hi_kids`, `ritu_hi_medical`, `ritu_hi_reels`, `ritu_hi_sales`, `ritu_hi_social`, `ritu_hi_social_lively`, `roopa_hi_companion`, `roopa_hi_conversational`, `roopa_hi_market`, `roopa_hi_narration`, `roopa_hi_recovery`, `sanchita_hi_ads_formal`, `sanchita_hi_ads_informal`, `sanchita_hi_assistant`, `sanchita_hi_banking`, `sanchita_hi_edtech`, `sanchita_hi_feedback`, `sanchita_hi_interview`, `sanchita_hi_kyc`, `sanchita_hi_market`, `sanchita_hi_romantic`, `sanchita_hi_social`, `sarika_hi_conversation`, `shalini_hi_companion`, `shalini_hi_social`, `shilpa_hi_narration`, `shreya_hi_conversational`, `shreya_hi_news`, `shruti_hi_edtech`, `shubh_hi_ads`, `shubh_hi_customer`, `shubh_hi_devotional`, `shubh_hi_ecomm`, `shubh_hi_recovery`, `shubh_hi_stories_dramatic`, `shubh_hi_stories_mixed`, `simran_hi_assistant`, `simran_hi_automobile`, `simran_hi_conversation`, `simran_hi_latenight`, `simran_hi_narration`, `simran_hi_news`, `simran_hi_news_breaking`, `simran_hi_recovery`, `simran_hi_sales`, `simran_hi_social_energetic`, `simran_hi_social_excited`, `suchitra_hi_ecomm`, `suhani_hi_social`, `suman_hi_companion`, `sumit_hi_conversational`, `sunny_hi_ads`, `sunny_hi_reels`, `tanya_hi_narration`, `tarun_hi_conversational`, `tarun_hi_sales`, `vaibhav_hi_social`, `vandana_hi_ecomm`, `vipul_hi_social` |
| `kn` — Kannada (4) | `chaitra_kn_conversation`, `chaitra_kn_narration`, `chetan_kn_conversation`, `suchitra_kn_narration` |
| `mr` — Marathi (9) | `ishita_mr_conversational`, `mrunal_mr_narration`, `mukul_mr_stories`, `neha_mr_narration`, `nilesh_mr_conversation`, `ritu_mr_insurance`, `ritu_mr_narration`, `rupali_mr_stories`, `soham_mr_narration` |
| `pa` — Punjabi (4) | `anand_pa_conversation`, `anand_pa_customer`, `harpreet_pa_narration`, `jaspal_pa_banking` |
| `ta` — Tamil (4) | `gokul_ta_narration`, `vetri_ta_ads`, `vetri_ta_suspense`, `vijay_ta_narration` |
| `te` — Telugu (4) | `kavitha_te_conversation`, `kavitha_te_narration`, `pooja_te_conversation`, `tarun_te_narration` |

Unlike a bad language code, a bad speaker is **not** substituted: the call ends before it starts,
with one log line naming the valid speakers. Substituting would answer the call in a voice nobody
chose. (Before this check the Sarvam plugin's own `ValueError` escaped the factory and killed the
job with a traceback instead.)

```json title="Valid"
{
  "assistant_tts_model": "sarvam",
  "assistant_tts_config": {
    "speaker": "shubh",
    "target_language_code": "hi-IN",
    "pace": 1.0
  }
}
```

```json title="Valid — bulbul:v4-flash"
{
  "assistant_tts_model": "sarvam",
  "assistant_tts_config": {
    "model": "bulbul:v4-flash",
    "speaker": "shubh_hi_customer",
    "target_language_code": "hi-IN",
    "pace": 1.0
  }
}
```

```text title="What a v2 speaker looks like in the worker log"
ERROR  Sarvam speaker 'anushka' is not available on bulbul:v3 for assistant asst_9f2 —
       bulbul:v3 speakers are: aayan, aditya, advait, amelia, amit, ashutosh, dev, ishita,
       kabir, kavitha, kavya, manan, neha, pooja, priya, rahul, ratan, ritu, rohan, roopa,
       rupali, shreya, shruti, shubh, simran, sophia, suhani, sumit, tanya, varun.
       Update assistant_tts_config.speaker.
```

The call then ends the same way any missing-key or bad-provider config does: one `ERROR` line,
no audio, nothing raised.

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
detail in [Cascade mode](../concepts/cascade.md#turn-detection).

## Internal models (not user-selectable, still billed)

| Feature | Model |
|---|---|
| Filler words (`assistant_interaction_config.filler_words`) | `gpt-4o-mini` |
| Native user-transcription (pipeline mode, `assistant_stt_model="native"`) | `gpt-4o-mini-transcribe` |

These run regardless of your chosen LLM/TTS provider and add their own token cost.
