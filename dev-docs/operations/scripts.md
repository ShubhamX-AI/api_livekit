# Scripts

Everything in `scripts/` is run by hand from the repo root with `uv run python scripts/<name>.py`.
The scripts read the same `.env` as the services (`src/core/config.py`), so check which MongoDB
(`MONGODB_URL`, `DATABASE_NAME`) and which OpenAI key you are pointing at before you run one.

There are two kinds:

- **Diagnostics** answer a question and change nothing, unless you pass `--apply` where offered.
- **Migrations and backfills** change stored documents. Most print a dry run by default and only
  write with `--apply`; the older ones write immediately. The tables say which is which.

The operator-facing story of what each diagnostic is for, and which symptom leads to it, is in
[troubleshooting](../../docs/reference/troubleshooting.md).

## Diagnostics

| Script | Question it answers | Command | Writes? | Exit code |
|---|---|---|---|---|
| `check_model_allowlist.py` | Does every allowlisted OpenAI model (`OPENAI_CASCADE_MODELS`, `OPENAI_REALTIME_MODELS`, `REALTIME_TRUNCATION_MODELS`) still exist for this key's account? Also lists served models we do not allowlist. Run it **before editing any model list** and after each `livekit-agents` bump. | `uv run python scripts/check_model_allowlist.py` (`--json` for one JSON object) | Never. No database; never prints the key. | 1 on drift, so it works as a pre-deploy gate |
| `check_model_allowlist.py --probe` | Does a model that is *listed* actually *answer*? OpenAI keeps deprecated ids in `/v1/models`. Sends one 16-token Responses request with `store: false`. | `uv run python scripts/check_model_allowlist.py --probe <model-id>` | Never | |
| `audit_assistant_models.py` | Which stored assistants hold an LLM model (or STT model) this deployment cannot run? Covers rows written before the API gate existed, models retired after the row was saved, and direct MongoDB edits. | `uv run python scripts/audit_assistant_models.py` (`--no-network` skips the OpenAI lookup) | Only with `--apply`: unsets `assistant_llm_config.model` (falls back to `gpt-4.1` in cascade, `gpt-realtime-1.5` in pipeline/realtime) and `assistant_stt_config.model` (falls back to `nova-3`). Never touches keys or knobs, never guesses a replacement. | 1 when anything unusable is found, so it works as a post-deploy check |
| `replay_cascade_request.py` | *Why* did OpenAI refuse this cascade assistant's request? The worker only logs `status_code=-1` because it talks over a WebSocket. This rebuilds the exact payload (`model_support.payload` + `model_support.tool_schema`), POSTs it over HTTPS where the error has detail, and bisects knob by knob when OpenAI names no parameter. | `uv run python scripts/replay_cascade_request.py <assistant_id>`; add `--show-payload` to print the body, `--bisect` to force the knob-by-knob pass (finds a second offender hiding behind the first) | Never. Reads one assistant and its tools; uses the assistant's own key or `OPENAI_API_KEY`; never prints the key. | 0 when OpenAI accepts, 1 when it refuses |
| `check_mermaid.py` | Does every Mermaid diagram in `docs/`, `dev-docs/` and `README.md` render? `mkdocs build --strict` cannot tell: diagrams are parsed in the reader's browser. Checks both parse errors (Mermaid's own `mermaid.parse` under jsdom) and diagrams that parse but draw wrong (a literal `\n` in a label). | `uv run python scripts/check_mermaid.py` (`--json` for JSON, `--lint-only` to skip the Node parser) | Never. No database or network, except npm fetching the Mermaid parser into a cache on first run. | 1 when a diagram fails; 2 when `node`/`npm` are missing (use `--lint-only` then) |

## Migrations and backfills

Every script below that has a dry run prints what it would change and writes nothing until you
pass `--apply` (or `--unset`, for `migrate_stt_config.py`). Run the dry run first and read it.

| Script | What it changes | When to run | Dry run? |
|---|---|---|---|
| `migrate_retired_models.py` | Moves `assistant_llm_config.model` (cascade) and `assistant_llm_config.backend_model` (duplex) off models removed from the allowlist on 2026-10-17: `gpt-5.1` to `gpt-6-sol`, `gpt-5.4-nano` to `gpt-6-luna`. A stored `reasoning_effort: "minimal"` becomes `"none"`, because GPT-6 refuses `minimal`. Nothing else on the row changes. Without it, the row keeps running until OpenAI retires the model on 2027-04-01, but every PATCH to it is refused. | After deploying 1.6.0 ([decision 0006](../decisions/0006-duplex-mode-gpt-6-and-new-speech-models.md)). Idempotent. | Yes. `--apply` writes. |
| `migrate_tts_settings.py` | Cleans stored TTS configs the API now refuses: retired ElevenLabs models (`eleven_monolingual_v1`, `eleven_multilingual_v1`) move to `eleven_multilingual_v2`; ElevenLabs voice settings the stored model does not read are removed; `temperature` on Sarvam `bulbul:v4-flash` (fixed at 0.6 by Sarvam) is removed. Only the v1 move changes what a caller hears; the rest unblocks editing. | After deploying 1.6.0. Until then the worker drops ignored settings at call time. Idempotent. | Yes. `--apply` writes. |
| `migrate_llm_knobs.py` | Drops cascade LLM knobs (`temperature`, `reasoning_effort`, `verbosity`) the stored model cannot read, for example `temperature` on `gpt-5-mini`. `create_llm` already drops them at call time; the row is still un-editable because `enforce_stored_mode_constraints` judges a PATCH against the merged row. Cascade rows only. | After deploying the model-gated knob rules. Idempotent. | Yes. `--apply` writes. |
| `migrate_stt_config.py` | Moves STT settings out of `assistant_interaction_config` (`user_stt_provider`, `stt_api_key`) into `assistant_stt_model` + `assistant_stt_config`. Uses the raw collection, because the legacy fields no longer exist on the Beanie model. | Two passes. Default pass copies; safe **before** deploying. `--unset` removes the old keys **after** the deploy is verified. Both idempotent. | No dry run. The default pass only copies, so it is safe; `--unset` is the destructive pass. |
| `migrate_assistant_mode.py` | Renames `assistants.assistant_llm_mode` to `assistant_mode` and `usage_records.llm_mode` to `mode`, with one idempotent `$rename` per collection. A hard break: the API refuses the old request key (`reject_retired_mode_key`). | **After** deploying the renamed code, then once more to catch documents old instances wrote during the deploy window. A run reporting 0 modified means it is done. Until it runs, a row missing `assistant_mode` behaves as `pipeline`. | No. Writes on every run. |
| `migrate_assistants.py` | Loads every assistant through Beanie and saves it back. The `Assistant` model's `model_validator(mode="before")` translates legacy flat fields into the nested `assistant_interaction_config`, so the save rewrites the stored shape. | Once, for databases that still hold the old flat assistant shape. | No. Writes every assistant. No docstring or flags. |
| `normalize_model_usage_providers.py` | Rewrites the `provider` spelling in `model_usage` on version-2 usage records through `normalize_provider` (for example `api.openai.com` becomes `openai`), and bumps `usage_schema_version`. | When old usage records carry provider names that pricing (`get_rate`) does not match. | Yes. `--apply` writes. |
| `backfill_billable_duration_minutes.py` | Sets `billable_duration_minutes` on `CallRecord`s missing it, using `calculate_billable_duration_minutes` from `src/core/billing.py`. Skips records with no duration and a non-billable status. | One-time, after billable duration was introduced. | No. Writes immediately. Run as `uv run python -m scripts.backfill_billable_duration_minutes`. |
| `backfill_call_records.py` | Sets `created_by_email` on `CallRecord`s missing it, copied from the owning assistant's `assistant_created_by_email`. | One-time, after `created_by_email` was added to call records. | No. Writes immediately. Run as `uv run python -m scripts.backfill_call_records`. |

## Notes

- `migrate_assistant_mode.py`'s docstring points at `src/api/models/api_schemas.py` for
  `reject_retired_mode_key`. That module is now a package; the function lives in
  `src/api/models/api_schemas/config/llm_config.py`.
- Two scripts are exercised by tests: `tests/test_migrate_retired_models.py` and
  `tests/test_migrate_tts_settings.py`. `tests/test_assistant_route.py` imports `legacy_to_stt`
  from `migrate_stt_config.py`, and `tests/test_model_allowlist.py` covers the allowlist checker.
