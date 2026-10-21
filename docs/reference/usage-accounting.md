# Usage accounting

Every call has one usage record, keyed by `room_name`, holding raw provider usage and an
estimated AI-provider cost. The estimate uses hardcoded public PAYG rates and is not an
invoice: negotiated discounts, credits, taxes, regional premiums, provider rounding and
telephony/recording/LiveKit costs are excluded.

The record reaches you four ways: the [end-of-call webhook](../api/calls/webhook.md), the
[per-call usage endpoint](../api/calls/usage.md), the `usage_records` collection directly, and
the user/admin analytics endpoints ([user summary](../api/analytics/tokens-summary.md),
[user by model](../api/analytics/tokens-by-model.md), [admin by model](../api/admin/tokens-by-model.md)).

## Where the numbers come from

The worker reads the usage the LiveKit agents SDK collected for the session. The SDK collects
it itself from the plugin metrics of every component the session owns, so nothing here makes
an extra provider call, and a self-hosted worker needs no Cloud credentials.

The SDK reports **one entry per `(provider, model)` pair**. Those entries are stored in
`model_usage` and summed into the flat columns. Metrics and model ids remain SDK-reported;
provider is normalized to one lowercase billing-vendor spelling at write time.

## Estimated Cost

New records contain `estimated_cost_usd`, `pricing_schema_version`, `pricing_complete`, and
`unpriced_model_usage`. Cost is calculated at every usage snapshot and again at teardown.
`pricing_complete=false` means at least one billable provider/model has no verified rate or
the usage dimensions needed to price it; the call still succeeds and the known entries are
included in the partial total. Unknown pricing is never represented as a misleading zero.

An OpenAI `service_tier` of `flex` prices a token-billed entry at half the standard rate, and
`fast` or `priority` at double. The tier applies to token-billed models only: in `duplex` mode it
scales the backend model and never the GPT-Live voice model, which is billed per second. An
unknown tier, or a tier on an OpenAI Realtime API model, leaves that entry unpriced.

### Duplex cost split

A `duplex` call bills two models, and `estimated_cost_usd` is their sum. The end-call webhook
`usage` object adds the two parts, for `duplex` calls only:

| Field | Meaning |
|---|---|
| `voice_model` | The GPT-Live voice model, such as `gpt-live-1`. |
| `backend_model` | The backend model as OpenAI reported it, snapshot date included. |
| `estimated_cost_voice_usd` | Voice model cost, from session seconds. |
| `estimated_cost_backend_usd` | Backend model cost, from tokens. `0` with the model listed in `unpriced_model_usage` means it has no rate. |

Every rate is listed on [Pricing](pricing.md). Gemini Live calls are priced too (list price per
1M tokens, per model). Cartesia and
Mistral are priced as well, so
every provider this platform can run now has a rate. Two of those numbers are weaker than the
rest and say so in the rate table: **Cartesia is derived** from its published plan tiers, since
it quotes no per-unit price, and **Deepgram is priced at its regular rate** while the page
shows a lower promotional one — an estimate that is a little high survives the promotion
ending.

Rates are versioned and static so a stored estimate remains reproducible. USD conversion for
providers whose source price is not USD uses the fixed conversion snapshot in the rate table;
only USD is exposed in the API. Historical schema-v1 records have no per-model source data and
are not backfilled.

`estimated_cost_usd` is also added to each priced `model_usage` entry. Analytics sums those
entry values by model; it does not attempt to price blended flat totals.

## Read `model_usage` for pricing

The flat columns exist for the dashboards that already aggregate on them. They sum across
models, so a call that swapped LLM mid-session reports one blended row and cannot be priced
correctly from those columns alone.

`model_usage` is the list the SDK produced, one dict per component instance:

```json
[
  {
    "type": "llm_usage",
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "input_tokens": 8400,
    "input_cached_tokens": 6144,
    "input_text_tokens": 8400,
    "input_cached_text_tokens": 6144,
    "input_cache_creation_tokens": 0,
    "output_tokens": 1230,
    "output_text_tokens": 1230,
    "session_duration": 0.0
  },
  {
    "type": "tts_usage",
    "provider": "cartesia",
    "model": "sonic-3",
    "characters_count": 485,
    "audio_duration": 32.5
  }
]
```

Every key is present even when zero, so a missing key means a schema change, never a zero.

**`provider` is normalized at write time.** Names are lowercased, and `api.openai.com` plus
any `*.openai.com` hostname becomes `"openai"`. Other names keep their lowercased spelling:
`"cartesia"`, `"deepgram"`, `"elevenlabs"`, `"sarvam"`, `"gemini"`, and `"vertex ai"` remain
distinct billing keys. Vertex AI is not folded into Gemini because they can bill separate
accounts. Existing v2 rows retain their old spellings until the normalization migration runs.
Entries are limited to the billable components — `llm_usage`, `tts_usage`, `stt_usage`. The
SDK also reports `eot_usage` for the turn detector; this deployment runs
`inference.TurnDetector(version="v1-mini")` locally, so it costs nothing and is not stored.

## Cached tokens are a subset

This is the easiest thing to get wrong, and it overcharges silently:

```text
input_cached_text_tokens  ⊆  input_text_tokens  ⊆  input_tokens
llm_total_tokens = input_tokens + output_tokens      # already contains the cached tokens
```

To price the input, split it:

```text
uncached_text = input_text_tokens - input_cached_text_tokens
cost = uncached_text * full_rate + input_cached_text_tokens * cached_rate
```

`input_cache_creation_tokens` is the exception. It counts tokens written *into* the cache,
which some providers bill on top of the read, so it is additive. OpenAI does not charge for
cache writes and reports `0`.

## What each mode records

| | `cascade` | `pipeline` | `realtime` |
|---|---|---|---|
| LLM tokens, including cached | yes | yes | yes |
| Modality split (audio/text/image) | text only | yes | yes |
| TTS characters and audio duration | yes | yes | not applicable — the model speaks |
| TTS tokens | never — see below | never | not applicable |
| STT | yes — Sarvam self-measured, the other four provider-reported | yes — the Sarvam tap (self-measured) or the Realtime API's own ASR | yes on OpenAI; **never** on Gemini, which reports none |

`tts_input_tokens` and `tts_output_tokens` are always `0`, on every provider this platform
can configure. The fields exist because `TTSModelUsage` carries them, but the SDK only fills
them only when a plugin reports token usage, and the sole plugin that does is OpenAI's TTS,
which this platform does not offer. Cartesia, Sarvam, ElevenLabs and Mistral are all billed by
character or by audio. Read `tts_characters_count` and `tts_audio_duration`; a zero in the
token fields means "not how this vendor bills", not "nothing was spoken".

`tts_characters_count` is exact for Cartesia and Sarvam, which stream. ElevenLabs and Mistral
are non-streaming and the SDK wraps them in a `StreamAdapter` that splits the reply into
sentences and synthesizes each one, so their count is the sum of the sentence lengths and can
read slightly below the string the assistant actually spoke.

## Sarvam STT is measured, not reported

This applies to both modes that can run Sarvam, for the same reason: the plugin's own
`RECOGNITION_USAGE` event carries whatever the server put in `metrics.audio_duration`. That
field is absent on some responses and defaults to `0.0`, and the plugin emits no event at all
for a turn whose transcript came back empty. Either way
the call would store a silent zero — indistinguishable from "no transcription ran", which is
the exact failure this accounting exists to remove. So the runtime counts the audio itself.

### Pipeline mode

`pipeline` mode transcribes on a parallel Sarvam connection that sits beside the session
rather than inside it, so nothing it emits reaches the SDK's usage collector. The worker
therefore counts the audio itself — the duration of every frame sent to Sarvam — and stores
the total as an STT entry shaped exactly like one the SDK would have produced. It reaches both
`stt_audio_duration` and the raw `model_usage` list.

Two consequences worth knowing before pricing off it:

- The number is what the tap **sent**, not what Sarvam reported back. Expect a small
  difference from the invoice, never a false zero.
- It is stream time, not speech time. Non-speech audio is silenced, not removed, so it still
  goes to Sarvam and is still counted — which matches how a continuously open connection is
  metered.
- The 2 s of silence sent to Sarvam at hangup (so the caller's last sentence comes back) is
  not counted.

### Cascade mode

Cascade puts the STT on the `AgentSession` as a real stage, so unlike the tap its usage does
reach the SDK's collector — with the wrong number in it. So the worker measures it the same
way as in pipeline mode, summing the duration of every frame sent to the STT stage, with the
same caveat: stream time, including silenced frames. The plugin's own figure is discarded, so
the audio is counted once.

The other four cascade providers are left alone. Cartesia, Deepgram and ElevenLabs count
frames themselves, and OpenAI is the only STT provider that reports billing **tokens** —
suppressing it would destroy the number the call is actually billed on.

One known shortfall, upstream and bounded: Deepgram `flux-general-*` and ElevenLabs flush
their usage collector every 5 s and never flush it again when the stream closes, so up to 5 s
per stream goes uncounted. Deepgram's `nova-*` family does flush, and additionally tops the
figure up with the connection's wall-clock lifetime. The shortfall is an undercount with a
known ceiling, always in the operator's favour, and never a zero — which is why it is
documented rather than worked around.

OpenAI STT has one configuration that would be unmeasurable, and the API now refuses it:
`use_realtime: false` takes the batch REST path, which reports no tokens at all. Only
`whisper-1` may use it, because that model is billed by audio duration and the batch path
measures duration locally. See [Compatibility](compatibility.md).

## Realtime transcription is billed separately from the realtime model

When a `realtime` call runs, or a `pipeline` call whose STT provider is not Sarvam, the
OpenAI Realtime API transcribes the caller with a separate ASR model
(`gpt-4o-mini-transcribe`) and bills it on that model's own pricing. It reports the usage on
every `conversation.item.input_audio_transcription.completed` event, but the LiveKit plugin's
handler keeps the transcript and drops the usage, so it reaches no collector.

The worker reads it off the plugin's raw event stream and stores it as an STT entry.
The numbers are OpenAI's own, not an estimate. It is token-billed, so
`stt_audio_duration` stays `0` and the tokens land in `stt_input_tokens` /
`stt_output_tokens`, split further into:

```text
stt_input_audio_tokens + stt_input_text_tokens  ==  stt_input_tokens
```

Both are subsets, never additional — the same rule as the cached LLM counts above. They are
separated because OpenAI charges a different rate for each, and any provider that does not
report the split leaves them at `0`.

`stt_provider` reads `openai` for two different things: the `cascade` OpenAI STT plugin, and
this ASR. `stt_model` separates them (`gpt-4o-mini-transcribe` here), so price on the
`(provider, model)` pair rather than on the provider alone.

**Gemini realtime reports no transcription usage at all**, and none is missing: its Live API
folds input audio into `prompt_tokens_details`, so that spend is already inside the LLM
token counts. A Gemini `realtime` call therefore stores `stt_provider = null` and zero STT
columns by design.

## When the record is written

The row is written repeatedly, always to the same `room_name`:

- **Every 15 s while the call runs**, and skipped when none of the counts moved since the last
  write — a call sitting on hold does not rewrite the same numbers.
- **Once at teardown**, after the last transcript has landed. This is the authoritative
  write, and the only one that sets `usage_finalized` to `true`.

Both go through the same upsert, so the snapshots cost nothing in accuracy: each one
overwrites the last, and the teardown write overwrites them all. `created_at` is set by the
write that creates the row and never moves afterwards.

`call_duration_minutes` is the one field a snapshot does not keep current. It grows on the
wall clock, so it is left out of the "did anything move" comparison — otherwise every call
would rewrite its row every 15 s whether or not it was doing anything. On a quiet call it
therefore lags behind the real elapsed time until the teardown write recomputes it. Read
`CallRecord` for a live duration; this field is for aggregation after the fact.

`usage_finalized` tells the two apart:

| `usage_finalized` | What it means |
|---|---|
| `true` | The call reached teardown. These are the final counts. |
| `false`, call still in progress | A mid-call snapshot. Correct as far as it goes, still growing. |
| `false`, call over | The worker died — crash, OOM kill, container restart — before teardown. The counts are everything the call had spent as of the last snapshot: a floor, not the bill. Up to 15 s of usage is missing, and `call_duration_minutes` stopped at the same moment. |

Before this existed the last case wrote nothing at all, and the end-of-call webhook shipped
with the `usage` block omitted entirely.

The admin analytics endpoints and the webhook include every row regardless of the flag — a
live call's tokens are real usage. Filter on `usage_finalized` yourself if you need only
settled calls.

## Schema versions

`usage_schema_version` says how much of the record to trust:

| Version | Meaning |
|---|---|
| `1` | Written before 2026-09. Flat LLM and TTS counts only; no cached totals, no token-billed STT/TTS fields, no `model_usage`. Every field added since reads `0` because it was never captured — treat it as unknown, not as zero. |
| `2` | Everything on this page, but `model_usage.provider` uses plugin spellings and may contain vendor casing or `api.openai.com`. |
| `3` | Everything on this page with normalized `model_usage.provider` values. New records use this version. |

Run `uv run python scripts/normalize_model_usage_providers.py` to preview the v2 migration, then
add `--apply` to rewrite only v2 rows and set them to version 3.

`sdk_version` records the `livekit-agents` version that produced the numbers, because what
the SDK reports changes between releases — `input_cache_creation_tokens`, for instance,
arrived in 1.6.10.

## When a record is all zeros

See [Troubleshooting](troubleshooting.md#usage-record-is-all-zeros).
