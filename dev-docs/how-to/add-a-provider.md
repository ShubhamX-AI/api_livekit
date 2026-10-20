# Add a provider

This recipe adds a new STT or TTS vendor (a "provider": Cartesia, Deepgram, Sarvam and so on). To
add a model to a vendor that already exists, use [Add a model](add-a-model.md).

A new **LLM** vendor is a bigger change: cascade only runs OpenAI (`openai.responses.LLM`), and
pipeline/realtime build their `RealtimeModel` inline in `src/core/agents/session.py`. Agree the
design with the user first, and extend the existing rule table rather than adding a second one
([decision 0004](../decisions/0004-one-rule-table-for-every-mode.md)).

Background for the files touched below:
[Speech and LLM stages](../subsystems/speech-and-llm-stages.md) and
[Validation and model support](../subsystems/validation-and-models.md).

## 0. Read the docs and confirm the plugin exists

Use the `livekit-docs` MCP server for the plugin's constructor, its model `Literal`, which mode
(streaming or batch) it uses, and whether it needs LiveKit Cloud. Anything that goes through the
LiveKit Inference gateway (`inference.STT`, `inference.TTS`, …) needs Cloud credentials and
**cannot** be used on this self-hosted deployment.

Then confirm the package resolves under the pinned SDK:

```bash
uv run python -c "import livekit.plugins.<vendor>"
```

## 1. Add the dependency to both manifests

- `pyproject.toml`: add the extra to `livekit-agents[...]` (or the plugin package).
- `docker/requirements-agent.txt`: the same change. The agent image installs from this file, not
  from `pyproject.toml`.
- `uv sync`.

The control image (`docker/requirements-control.txt`) must **not** gain `livekit-agents`.

## 2. Add the system key setting

- `src/core/config.py` (`Settings.__init__`): `self.<VENDOR>_API_KEY = os.getenv("<VENDOR>_API_KEY", "")`.
  This is the only module that reads the environment.
- `.env.example`: add `<VENDOR>_API_KEY=` with no value.
- `README.md`: add the variable to the environment table.

## 3. Register the provider in `src/core/model_support/speech.py`

- `STT_ENV_KEYS` or `TTS_ENV_KEYS`: map the provider name to `"<VENDOR>_API_KEY"`.
  `enforce_provider_keys` in `src/api/validation/assistant_guard.py` reads these maps, so a
  keyless provider is refused at the API without further code.
- If the provider takes a `model` field: add a `<VENDOR>_STT_MODELS` / `<VENDOR>_TTS_MODELS`
  frozenset, copied from the plugin's `Literal`, and register it in `STT_MODELS_BY_PROVIDER` /
  `TTS_MODELS_BY_PROVIDER`. A provider with no entry is treated as "model pinned in the factory".

Keep this module dependency-free: do not import the plugin here.

## 4. Add the request schema

In `src/api/models/api_schemas/config/stt_config.py` or `tts_config.py`:

1. Add a `<Vendor>STTConfig` / `<Vendor>TTSConfig` class with:
   - `model_config = ConfigDict(extra="forbid")` (every provider config has it; a typo is a 422);
   - `type: Literal["<vendor>"] = "<vendor>"` as the discriminator;
   - `api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, ...)`
     ([decision 0003](../decisions/0003-never-echo-secrets-in-errors.md) explains the 500 cap);
   - every knob as `Optional[...]` with bounds that mirror the vendor's own limits. Absent must mean
     "SDK default".
   - a `model` field validated with `check_stt_model` (STT) or `unsupported_speech_model_reason`.
2. Add the class to the `STTConfig` / `TTSConfig` `Union`.
3. Export it from `src/api/models/api_schemas/__init__.py`.

Then add the provider name to the `Literal` on `assistant_stt_model` / `assistant_tts_model` in
**both** `CreateAssistant` and `UpdateAssistant` in `src/api/models/api_schemas/assistant.py`.
`inject_provider_type` fills in `type` from that field, so no further wiring is needed.
Update the comment on `assistant_stt_model` / `assistant_tts_model` in
`src/core/db/db_schemas.py`.

## 5. Add the mode rules

`validate_mode_config` in `src/api/models/api_schemas/config/llm_config.py` is the one rule table.

- A plugin STT is **cascade-only**. Add the name to the cascade branch's error message that lists
  the valid STT providers.
- In pipeline mode `resolve_stt` (`src/core/agents/stt/factory.py`) decides what happens: add the
  key to its `key_var` map, and decide whether the provider runs as a parallel tap or collapses to
  `native` (as `openai` does).

## 6. Build the plugin in the factory

- STT: a new `if model == "<vendor>":` branch in `create_stt` (`src/core/agents/stt/factory.py`).
- TTS: a new branch in `create_tts` (`src/core/agents/tts/factory.py`) and an entry in
  `_TTS_ENV_KEYS` there; resolve the key with `_resolve_api_key`.

Rules the existing branches follow:

- Resolve `config.api_key or settings.<VENDOR>_API_KEY` **before** constructing the plugin, and
  return `None` with one `logger.error` line when there is none. A constructor that raises escapes
  `entrypoint()` and kills the job.
- Forward a knob only when its config value is not `None`. When the plugin uses a sentinel for
  "not set", pass `NOT_GIVEN`, never `None` (see the ElevenLabs `voice_settings` note in
  [decision 0002](../decisions/0002-optional-tts-and-cascade-llm-knobs.md)).
- Pin the model explicitly instead of relying on the plugin default. Plugin defaults change
  between SDK versions.
- Validate language codes before passing them (`src/core/agents/stt/lang.py`); several plugins
  raise on a code they do not speak.

## 7. Price it

- Add a `<VENDOR>_STT_RATES` / `<VENDOR>_TTS_RATES` table in `src/core/pricing/rates.py` and
  register it in `get_rate` under `("stt_usage" | "tts_usage", "<provider>")`.
- The provider key must match what the plugin reports in `session.usage` after
  `normalize_provider` (`src/core/agents/usage.py`) lowercases it. Check it on a real call.
- If the plugin's own usage numbers cannot be trusted, meter the stage yourself, as Sarvam does
  (`src/core/agents/stt/cascade_usage.py`).
- Add every rated model to `docs/reference/pricing.md`.

## 8. Tests

Add, then run:

```bash
uv run python -m unittest tests/test_speech_models.py tests/test_provider_pricing.py \
  tests/test_cascade_config.py tests/test_provider_key_guard.py tests/test_assistant_schemas.py -v
uv run python -m unittest discover -s tests
```

- `tests/test_speech_models.py`: a parity test that reads the plugin's `Literal` and compares it
  with your frozenset (copy `TestSTTModelSetsMatchThePlugins.test_cartesia`).
- `tests/test_provider_pricing.py`: every allowlisted model of the new provider has a rate.
- `tests/test_cascade_config.py`: the factory builds the plugin with the right arguments, and
  returns `None` without a key.
- `tests/test_provider_key_guard.py`: the API refuses the provider when no key exists.
- `tests/test_assistant_schemas.py`: unknown keys are a 422, bounds hold.

All tests run offline. Mock the plugin constructor; never call the vendor.

## 9. Docs

`grep -rn "deepgram" docs/ README.md` (or another sibling provider) finds every page to update. At
least:

- `docs/reference/models.md`, `docs/reference/compatibility.md`,
  `docs/reference/troubleshooting.md`, `docs/reference/pricing.md`
- `docs/concepts/cascade.md` and [`../subsystems/speech-and-llm-stages.md`](../subsystems/speech-and-llm-stages.md)
  (these replace `docs/architecture/cascade-pipeline.md`)
- `docs/api/assistant/create.md`, `update.md`, `index.md`, `list.md`
- `README.md` (environment table, provider list) and `docs/features.md`
- the "Key env vars" and provider lists in `AGENTS.md`

Then:

```bash
uv run mkdocs build --strict
uv run python scripts/check_mermaid.py
uvx ruff check <the files you touched>
```

## Where in the code

| What | File | Symbol |
|---|---|---|
| Env keys and model sets | `src/core/model_support/speech.py` | `STT_ENV_KEYS`, `TTS_ENV_KEYS`, `STT_MODELS_BY_PROVIDER`, `TTS_MODELS_BY_PROVIDER` |
| Request schemas | `src/api/models/api_schemas/config/{stt,tts}_config.py` | `STTConfig`, `TTSConfig` |
| Provider name `Literal` | `src/api/models/api_schemas/assistant.py` | `CreateAssistant`, `UpdateAssistant`, `inject_provider_type` |
| Mode rules | `src/api/models/api_schemas/config/llm_config.py` | `validate_mode_config` |
| Keyless refusal | `src/api/validation/assistant_guard.py` | `enforce_provider_keys` |
| Plugin construction | `src/core/agents/stt/factory.py`, `src/core/agents/tts/factory.py` | `create_stt`, `resolve_stt`, `create_tts`, `_resolve_api_key` |
| Rates | `src/core/pricing/rates.py` | `get_rate` |
| Usage provider spelling | `src/core/agents/usage.py` | `normalize_provider` |
| Settings | `src/core/config.py` | `Settings` |
