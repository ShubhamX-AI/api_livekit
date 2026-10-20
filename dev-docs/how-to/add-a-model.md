# Add a model

This recipe adds a new model id to a provider that is already wired up: an OpenAI LLM for
cascade, realtime/pipeline or the duplex backend; a Gemini Live model; or an STT/TTS model id. If
the *vendor* is new, follow [Add a provider](add-a-provider.md) instead.

Why it takes several files: every model id is checked in four places before a call can use it
(Pydantic, the per-mode rule table, "does OpenAI still serve it", "will OpenAI accept this
request"), it has to be priced, and it is listed in several public pages. Background:
[Validation and model support](../subsystems/validation-and-models.md).

## 1. Ask the API what exists. Never work from memory.

```bash
uv run python scripts/check_model_allowlist.py
uv run python scripts/check_model_allowlist.py --probe <new-model-id>
```

The first command compares every OpenAI allowlist (`OPENAI_CASCADE_MODELS`,
`OPENAI_REALTIME_MODELS`, `REALTIME_TRUNCATION_MODELS`) against `GET /v1/models` for this key, and
lists chat and realtime models the account serves that we do not allowlist. It exits 1 on drift.

The second sends one 16-token Responses request (`store: false`) for the new id.

Why both: OpenAI retires models on its own schedule, and a stale entry looks exactly like a working
one until a call goes silent. That is how the three `*-chat-latest` aliases became an outage
([decision 0001](../decisions/0001-ask-openai-before-storing-a-config.md)). Being *listed* is not
enough either: OpenAI keeps deprecated ids in `/v1/models` after they stop answering, so only
`--probe` proves the model works.

For a non-OpenAI model there is no such script. Read the installed plugin's own `Literal`
(for example `livekit.plugins.google`, `livekit.plugins.deepgram.models`) and the vendor's live
docs through the `livekit-docs` MCP server.

## 2. Add the id to the allowlist in `src/core/model_support/`

This package is dependency-free (stdlib, `httpx`, `src.core.config`, `src.core.logger` only)
because both Docker images import it. Do not import `livekit` or `fastapi` here.

Spell every id out. Never match by prefix: `gpt-5.2-chat-latest` was a chat model, not a
reasoning model.

| Model kind | File | Symbol to edit |
|---|---|---|
| OpenAI reasoning model (cascade, duplex backend) | `capabilities.py` | `REASONING_MODELS` |
| OpenAI chat model (cascade) | `capabilities.py` | `CHAT_MODELS` |
| OpenAI realtime model (pipeline, realtime) | `capabilities.py` | `REALTIME_GA_MODELS` |
| GPT-Live model (duplex) | `capabilities.py` | `GPT_LIVE_MODELS` |
| Gemini Live model (realtime) | `capabilities.py` | `GEMINI_LIVE_MODELS` (or `GEMINI_VERTEX_ONLY_MODELS` if it needs Vertex) |
| STT model id | `speech.py` | `SARVAM_STT_MODELS`, `CARTESIA_STT_MODELS`, `DEEPGRAM_STT_MODELS`, `ELEVENLABS_STT_MODELS` or `OPENAI_STT_MODELS` |
| TTS model id | `speech.py` | `ELEVENLABS_TTS_MODELS`, or `SARVAM_TTS_MODELS` + `SARVAM_SPEAKERS_BY_MODEL` |

`OPENAI_CASCADE_MODELS` and `OPENAI_REALTIME_MODELS` in
`src/api/models/api_schemas/config/llm_config.py` are aliases of these sets. Do not edit them
separately.

## 3. Record which knobs the model accepts

For an OpenAI LLM, `temperature`, `reasoning_effort` and `verbosity` are model-gated. A wrong
pairing is a 400 on every turn. Check, in `src/core/model_support/capabilities.py`:

- `REASONING_TOOL_INCOMPATIBLE`: does the model reject `reasoning.effort` when tools are attached?
- `PLUGIN_INJECTS_REASONING`: does `openai.responses.LLM` inject a reasoning effort on its own
  for this model? `create_llm` in `src/core/agents/llm/factory.py` undoes that injection.
- `SERVICE_TIER_FLEX_MODELS`: may it use `service_tier: "flex"`? Today this is defined as
  `REASONING_MODELS`; if the new model breaks that rule, split the set.
- `REALTIME_TRUNCATION_MODELS`: for realtime ids, does it take `session.truncation`?

Write down how you verified each answer in a comment beside the set (the existing comments record
the date and the probe used). Which `reasoning_effort` *values* a model accepts is not stored
anywhere: gate 4 asks OpenAI at create/update time.

For a speech model, check the per-model settings:

- ElevenLabs: add an entry to `ELEVENLABS_UNREAD_SETTINGS` in `speech.py` listing the
  `voice_settings` keys the model ignores (from ElevenLabs' `/v1/models` flags).
- Deepgram: decide the family. `nova-*` builds `deepgram.STT`, `flux-*` builds `deepgram.STTv2`
  in `create_stt` (`src/core/agents/stt/factory.py`).
- OpenAI STT billed by duration rather than tokens: add it to `OPENAI_STT_DURATION_BILLED_MODELS`.

## 4. Check the per-mode rule table

`validate_mode_config` in `src/api/models/api_schemas/config/llm_config.py` reads the sets above,
so a new id in an existing set usually needs no change here. Change it only if the model brings a
new rule (a knob it refuses, a mode it cannot run in). Never add a second rule table.

## 5. Price it

Add a rate to the right table in `src/core/pricing/rates.py` (`OPENAI_RATES`,
`OPENAI_REALTIME_RATES`, `GEMINI_LIVE_RATES`, `DEEPGRAM_RATES`, `ELEVENLABS_TTS_RATES`, …) with the
date you read the vendor's price. An accepted model with no rate prices the whole call as zero.

Then add the id, in backticks, to `docs/reference/pricing.md`.

## 6. Change the default only if asked

Defaults (`DEFAULT_CASCADE_MODEL`, `DEFAULT_REALTIME_MODEL`, `DEFAULT_GEMINI_LIVE_MODEL`,
`DEFAULT_DUPLEX_BACKEND_MODEL` in `capabilities.py`) move every assistant that omits `model`. That
is the user's decision, not part of adding a model.

## 7. Run the tests

```bash
uv run python -m unittest tests/test_model_allowlist.py tests/test_provider_pricing.py \
  tests/test_speech_models.py tests/test_realtime_capabilities.py tests/test_cascade_config.py -v
uv run python -m unittest discover -s tests
```

What each one catches:

| Test | Fails when |
|---|---|
| `tests/test_provider_pricing.py` | an allowlisted model has no rate, or a rated model is missing from `docs/reference/pricing.md` |
| `tests/test_speech_models.py` | a speech allowlist drifts from the installed plugin's `Literal`, or a Deepgram id has no rate |
| `tests/test_realtime_capabilities.py` | `GEMINI_LIVE_MODELS` + `GEMINI_VERTEX_ONLY_MODELS` stop matching the Google plugin |
| `tests/test_model_allowlist.py` | the allowlist checker's report logic breaks |

Add a test for any new rule from step 3 or 4 (for example in `tests/test_cascade_config.py` or
`tests/test_duplex_mode.py`).

## 8. Update every page that lists models

`grep -rn "<a sibling model id>" docs/ README.md` finds them all. At least:

- `docs/reference/models.md` (keep the "what changes if you change it" column)
- `docs/reference/compatibility.md`
- `docs/reference/troubleshooting.md`
- `docs/reference/pricing.md`
- `docs/concepts/cascade.md` and [`../subsystems/speech-and-llm-stages.md`](../subsystems/speech-and-llm-stages.md)
  (these replace `docs/architecture/cascade-pipeline.md`)
- `docs/api/assistant/create.md`, `update.md`, `index.md`, `list.md`
- `README.md` and `docs/features.md` if the feature list changes

## 9. Build and lint

```bash
uv run mkdocs build --strict
uv run python scripts/check_mermaid.py
uvx ruff check <the files you touched>
```

## 10. After deploying

```bash
uv run python scripts/audit_assistant_models.py
```

If you *removed* a model, write a migration like `scripts/migrate_retired_models.py` that moves
stored rows to a replacement, and keep the old rate so past calls still price.

## Where in the code

| What | File | Symbol |
|---|---|---|
| LLM model sets and knob rules | `src/core/model_support/capabilities.py` | `REASONING_MODELS`, `CHAT_MODELS`, `REALTIME_GA_MODELS`, `GEMINI_LIVE_MODELS`, `unsupported_knob_reason` |
| Speech model sets | `src/core/model_support/speech.py` | `STT_MODELS_BY_PROVIDER`, `TTS_MODELS_BY_PROVIDER`, `unsupported_speech_model_reason` |
| Rule table | `src/api/models/api_schemas/config/llm_config.py` | `validate_mode_config` |
| Live OpenAI gates | `src/core/model_support/openai_live.py` | `unavailable_model_reason`, `rejected_config_reason` |
| Rates | `src/core/pricing/rates.py` | `get_rate` and the `*_RATES` tables |
| Runtime knob filtering | `src/core/agents/llm/factory.py` | `create_llm`, `create_gpt_live` |
