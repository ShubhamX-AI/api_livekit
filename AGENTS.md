# AGENTS.md — Shared notes for coding agents

This file is read by all agents (opencode, Claude Code) working in this repo. It
complements `CLAUDE.md` (project overview) by tracking **recent cross-cutting
changes** so other agents do not reintroduce regressions, and records the
system-of-record for each topic.

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