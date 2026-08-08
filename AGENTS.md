# AGENTS.md — Shared notes for coding agents

This file is read by all agents (opencode, Claude Code) working in this repo. It
complements `CLAUDE.md` (project overview) by tracking **recent cross-cutting
changes** so other agents do not reintroduce regressions, and records the
system-of-record for each topic.

## Working agreement (do this before touching anything)

Applies to any **non-trivial** request — one that touches 2+ files or needs 3+ steps. A one-line
fix, a rename, or a plain question skips all of it; do those directly.

1. **Check the skills first.** Before planning, see whether an available skill already covers the
   task. If one fits, invoke it and follow it instead of improvising a workflow. The same goes for
   the `livekit-docs` MCP server: for anything about the LiveKit SDK, plugins, or model parameters,
   read the live docs — never work from memory, the SDK moves faster than any snapshot.
2. **Write the todo list before the first edit.** Lay out the steps, keep exactly one in progress,
   mark each done as it lands. The list is the plan; write it while the work is still reversible,
   not as a summary afterwards.
3. **Ask when something is genuinely undecided.** Ask the user when two readings of the request
   lead to materially different work, when the request contradicts what is already in the repo (a
   doc, a validation rule, a stored schema), or when a choice is theirs to make (defaults, naming,
   scope, whether to drop a provider). Ask *before* building on the guess. Do **not** ask about
   things with an obvious default — pick it, say which, and move on.
4. **Then work the list step by step**, verifying as you go rather than at the end.
5. **Finish the whole chain.** A change is not done until code, schemas, tests and docs agree —
   see [Definition of done](#definition-of-done).

Same block lives in `CLAUDE.md` — edit both or neither.

## Definition of done

A change to models, providers or config knobs is finished only when all of these are true:

- Factory code, `src/api/models/api_schemas/`, and the `validate_mode_config` rule table agree.
- Tests updated and green: `uv run python -m unittest discover -s tests`.
- Docs updated in **every** place that lists the thing you changed: `docs/reference/models.md`,
  `docs/reference/compatibility.md`, `docs/architecture/cascade-pipeline.md`,
  `docs/api/assistant/{create,update,index,list}.md`, plus `README.md` / `docs/features.md`
  when the feature list changes. `grep` for a sibling provider's name to find them all.
- Docs build clean: `uv run mkdocs build --strict`.
- Lint the files you touched: `uvx ruff check <paths>` — pre-existing violations live outside
  them; don't reflow unrelated files.
- **Never `git commit` unless explicitly asked.**

## Rule of thumb: where truth lives

| Topic | Source of truth |
|---|---|
| Models, providers, config defaults, values, change-effects | `docs/reference/models.md` (auto-doc'd from the factories) |
| Every config knob for create/update, examples, defaults | `docs/api/assistant/create.md`, `docs/api/assistant/update.md` |
| Cascade mode specifics + validation rules | `docs/architecture/cascade-pipeline.md` |
| Which mode × LLM × STT × TTS combinations are legal | `docs/reference/compatibility.md` |
| Runtime configuration schemas + allowlists | `src/api/models/api_schemas/` (`config/llm_config.py` for both OpenAI allowlists and the per-mode rule table) |
| LLM / TTS / STT build logic | `src/core/agents/{llm,tts,stt}/factory.py` |

If a doc disagrees with the factory code, **the factory code wins** — fix the doc.

## Recent changes — the assistants' TTS + cascade LLM knobs (2026-08)

New optional `assistant_tts_config` and `assistant_llm_config` keys. All are
optional; **omitting one keeps the old behavior / SDK default** (that preserves
existing assistants). When you touch these, keep behavior identical when the key
is absent.

### TTS providers (`assistant_tts_config`)

- **Cartesia**: `speed` (float `0`–`3`, def `1.0` — preset strings rejected, `sonic-3` needs a float), `volume`
  (def `1.0`), `emotion` (Sonic 3 only), `language` (def `en`),
  `pronunciation_dict_id`. Factory: `src/core/agents/tts/factory.py`.
- **Sarvam**: `pace` (def `1.0`), `speech_sample_rate` (def `24000`),
  `temperature` (def `0.3`), `target_language_code`. Defaults match the SDK —
  do not change them.
- **ElevenLabs**: `model` (def `eleven_v3`), `voice_settings` (subkeys
  `stability`, `similarity_boost`, `style`, `speed`, `use_speaker_boost`).
  **CRITICAL: when `voice_settings` is absent, pass `NOT_GIVEN`, never `None`** —
  the client treats `None` as "set" and `dataclasses.asdict(None)` crashes on
  synthesis. See the regression tests in `tests/test_cascade_config.py`.

### Cascade LLM (`assistant_llm_config`, mode=`cascade`, build = `openai.responses.LLM`)

- `model` **must** be in `OPENAI_CASCADE_MODELS` allowlist
  (`src/api/models/api_schemas/config/llm_config.py`); unknown → `422`. Default `gpt-4.1`.
- `temperature` (0–2): **ignored by reasoning models** (`gpt-5`/`gpt-5.x`) —
  they take `reasoning_effort` instead. Do not show both on a reasoning model in
  examples.
- `reasoning_effort`: `none|minimal|low|medium|high|xhigh|max`, reasoning
  models only.
- `max_output_tokens`, `service_tier`, `verbosity`, `tool_choice`,
  `parallel_tool_calls`: forwarded when set; omitted keeps SDK default.
- Factory only forwards a knob when its config value is **non-None** (or truthy
  for strings/bools).

Keep the "what changes if you change it" per-column style already in
`docs/reference/models.md` — it is what users rely on.

## Recent changes — secret redaction + key caps (2026-08)

- **Error responses never echo secrets.** `redact_text` in `src/core/providers/keys.py`
  scrubs secret-shaped substrings out of any exception message before it reaches an HTTP
  body (labelled `api_key=…`/`Authorization: Bearer …` assignments, key prefixes
  `sk-proj-`/`sk-ant-`/`AIza`/`ghp_`, bare `Bearer <jwt>`, and 32+-char opaque tokens).
  `redact_validation_errors` masks a failing field's `input` when the field `loc` is a
  secret name (and any nested dict value whose key is secret). Endpoints must not
  interpolate a raw exception into `detail` — run it through `redact_text` first.
- **Provider key cap is now 500 characters** on every `api_key` field (was 100 on
  STT/TTS, 200 on LLM). `ProviderApiKey` stays an `Annotated` type; the per-field
  `max_length=500` is intentional so validation errors name the offending field.

## Recent changes — mode guardrails (2026-08)

Combinations that used to be accepted and then failed at call time are now rejected
at the API. If you add a provider or a mode, extend the same rule table — do not add
a second one.

- **`validate_mode_config(mode, llm_config, stt_model)`** in
  `src/api/models/api_schemas/config/llm_config.py` is the single rule table for all
  three modes. Called by both `CreateAssistant` and `UpdateAssistant` validators.
- **`enforce_stored_mode_constraints`** in `src/api/routes/assistant.py` re-runs that
  same table against `stored row + PATCH`, so a mode switch cannot land a combination
  the request alone looked fine for. `400`, not `422` — the request is well-formed, the
  merge is not.
- **Gemini is rejected in `pipeline` and `cascade`.** Google's Live API cannot run the
  text-only modality half-cascade needs on native-audio models
  (googleapis/python-genai#1780). The pipeline Gemini branch in `session.py` is gone.
  Realtime Gemini is untouched and fully supported.
- **Two model allowlists**: `OPENAI_REALTIME_MODELS` (pipeline + realtime) and
  `OPENAI_CASCADE_MODELS` (cascade). They do not overlap. Gemini realtime IDs stay
  free-form on purpose.
- **`extra="forbid"` is now on every provider config** — all five STT shapes and all
  four TTS shapes, not just some. A typo is a `422`.
- **Missing API keys are checked before the plugin is constructed** in *both* factories.
  `create_tts` returns `None` like `create_stt` already did, instead of letting a plugin
  constructor raise out of `entrypoint()`.
- **`CartesiaTTSConfig.speed` is float-only.** The preset strings (`slow`/`normal`/`fast`)
  were accepted by the schema but `sonic-3` — the pinned model — raises
  `ValueError: speed must be a float for sonic-3` inside the plugin constructor. Do not
  re-add them without also un-pinning the model.
- **Deepgram is two plugin classes.** `nova-*` -> `deepgram.STT` (/listen/v1), `flux-*` ->
  `deepgram.STTv2` (/listen/v2, `language_hint` instead of `language`). Neither validates the
  model at construction, so `create_stt` dispatches on the name. Adding a Deepgram model means
  checking which family it belongs to.
- **OpenAI STT streams only if you ask.** The plugin's `use_realtime` defaults to `False`
  (batch REST, no interim results); `create_stt` passes `True` because a live call needs
  streaming. `gpt-realtime-whisper` is rejected outright — it has no server-side endpointing
  and the plugin then requires a `livekit-plugins-silero` VAD, which is not installed (the
  session's VAD is `inference.VAD`, which an STT plugin cannot take).
- **`assistant_stt_model="openai"` means two different things per mode.** Cascade builds the
  real OpenAI STT plugin; pipeline collapses it to `native` (same vendor, same model, one less
  connection) — which also keeps pre-migration rows working.
- **Sarvam TTS numeric bounds mirror the provider**, verified against the LiveKit Sarvam TTS
  page: `pace` 0.3-3.0, `temperature` 0.01-2.0 (not 0.0), `speech_sample_rate` an enum of
  8000/16000/22050/24000/32000/44100/48000 rather than a range.
- **`SarvamTTSConfig.target_language_code` defaults to `None`**, not `bn-IN`. The field is
  always serialized, so a concrete default silently overrode the factory's `en-IN`
  fallback for every assistant that omitted it.

## process notes

- Run tests: `uv run python -m unittest discover -s tests -v`; always green.
- Strict docs build to catch broken links/nav: `uv run mkdocs build --strict`.
- Lint: `uvx ruff check .` / `uvx ruff format .`. Pre-existing violations live
  outside the files you touch; don't reflow unrelated files.