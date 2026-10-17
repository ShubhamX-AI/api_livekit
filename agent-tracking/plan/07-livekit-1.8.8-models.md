# 07 — livekit-agents 1.8.8, GPT-6, GPT-Live duplex, ElevenLabs v4, Sarvam bulbul:v4-flash

Status: **code complete; step 8 (manual calls) open** (approved 2026-10-17) · written 2026-10-17 · research:
`agent-tracking/research/03-livekit-1.8.8-models-and-features.html` (§7b has the measurements
this plan relies on).

## Goal

Let an assistant choose the models that became available in livekit-agents 1.8.3 to 1.8.8 and
that this self-hosted deployment can actually run. Every new choice must be validated at
create/update, priced, tested, and documented.

## Agreed scope

| Item | Decision |
|---|---|
| SDK bump | `livekit-agents~=1.8.8` |
| Cascade LLMs | add `gpt-6-luna` and `gpt-6-sol`. `gpt-6-astra` and `gpt-6.1-sol` are out, because LiveKit does not document them |
| Realtime models | add `gpt-realtime-2.1` and `gpt-realtime-2.1-mini` (pipeline and realtime modes) |
| GPT-Live | new `assistant_mode="duplex"` on `openai.realtime.GPTLiveModel` |
| Duplex with greeting audio enabled | **reject with 422** at create/update |
| ElevenLabs TTS | add `eleven_v4` and `eleven_v4_turbo` |
| Sarvam TTS | new optional `model` field: `bulbul:v3` (default) or `bulbul:v4-flash`, with the **full** v4-flash speaker roster |
| Out of scope | answering machine detection, Gemini 4 Argon, `gpt-live-transcribe`, Google Gemini STT, LLM FallbackAdapter |

## Evidence already gathered

- `uv run python scripts/check_model_allowlist.py` (valid key, 2026-10-17) exited 0. The account
  serves `gpt-6-luna`, `gpt-6-sol`, `gpt-live-1`, `gpt-realtime-2.1` and `gpt-realtime-2.1-mini`.
  Every model already on the allowlist is still served, including the default `gpt-realtime-1.5`.
- Direct `/v1/responses` probes: `gpt-6-luna` and `gpt-6-sol` behave exactly like the control
  `gpt-5.6-luna`. They accept `reasoning.effort` none/low/medium/high/xhigh (also with tools),
  `text.verbosity`, and `service_tier` flex/priority. They reject `temperature` (400
  `Unsupported parameter`) unless effort is `none`, and they reject effort `minimal`. So they
  belong in `REASONING_MODELS` only: not in `REASONING_TOOL_INCOMPATIBLE`, and not in
  `PLUGIN_INJECTS_REASONING`, because the plugin's `_supports_reasoning_effort` on main does not
  list them.
- Sarvam plugin on main: `bulbul:v4-flash` has its own roster (`BULBUL_V4_FLASH_SPEAKERS`, about
  220 names that share none with v3). It also has stricter bounds (`_V4_PARAM_BOUNDS` in
  `sarvam/tts.py`: pace 0.5–2.0, temperature 0.01–1.0) and allows only 8000/16000/22050/24000 Hz
  when streaming.
- The longest v4-flash speaker name, `ishita_enhi_customer_expressive`, is 31 characters. Today
  `SarvamTTSConfig.speaker` has `max_length=30`
  (`src/api/models/api_schemas/config/tts_config.py:37`), so that field has to grow.

## Design notes (system design pass)

- **Numbers.** No change to load. GPT-Live keeps one WebSocket per call, as the realtime mode
  does. `MAX_CONCURRENT_*` is unchanged.
- **Data and invariants.** No migration. `assistant_mode` is a plain string in the DB
  (`src/core/db/db_schemas.py`). The new Sarvam `model` field defaults to `bulbul:v3`, so
  existing rows keep their behaviour. Invariant: a stored row never holds a config that the
  provider refuses on every turn, which is the four gates in CLAUDE.md.
- **Compatibility.** The changes only add things. Old clients that send no `model` for Sarvam
  get v3. A worker on 1.8.2 that receives a `duplex` row falls into the existing
  unknown-mode branch (`session.py:301-309`, treated as pipeline). That is why deploy order
  matters: agent image first, then the API (see Delivery).
- **Failure modes of outbound calls.**
  - GPT-Live WebSocket drop: the plugin reconnects and replays the history.
  - GPT-Live refusing the greeting: `generate_reply` is treated as refused after 10 s and the
    handle ends with `RealtimeError`. We log it and the call continues, because the caller can
    still speak first.
  - Sarvam v4-flash with a speaker not on its roster: the plugin raises at construction. Gate 1
    catches it at the API and `validate_sarvam_speaker` catches it at call time, as it already
    does for v3.
- **Observability.** Log one line at session start: `Duplex mode | model=gpt-live-1 |
  backend=<model> | voice=<voice>`. Usage needs no new fold: `summarize_usage` already totals
  `session_duration` across llm entries (`src/core/agents/usage.py:93`), and the backend
  model's tokens arrive as ordinary `LLMMetrics`.
- **Limits.** GPT-Live startup history holds at most 128 messages / 8192 tokens, so the inbound
  context we inject must fit. The plugin drops the oldest messages first. This is acceptable
  and gets documented.

## Duplex mode: interface

`assistant_mode="duplex"`, provider `openai` only. `assistant_llm_config` fields:

| Field | Rule |
|---|---|
| `model` | `gpt-live-1` only (new set `GPT_LIVE_MODELS`); default `gpt-live-1` |
| `voice` | GPT-Live voice set, read from the 1.8.8 plugin (`cedar` replaces `aster`); default `marin` |
| `backend_model` | one of `REASONING_MODELS`; default `gpt-5.6-luna` (the plugin default) |
| `backend_instructions` | optional `str`, max 4000. When unset, the default is a short built-in instruction: "handle delegated work, use tools when current data is needed, answer in one short sentence the voice can read out" |
| `reasoning_effort`, `verbosity`, `service_tier`, `tool_choice` | apply to the backend model and are checked with the same `_validate_cascade_knobs` rules against `backend_model` |
| `temperature` | rejected |

Ignored in duplex: `assistant_tts_model`/`_config` and `assistant_stt_model`/`_config`, as in
realtime mode.

Rejected with 422 in duplex:
- `assistant_greeting_audio.enabled=true`, because `session.say()` raises with no TTS attached.
- `text_only` web calls, because GPT-Live is audio only. This copies the existing realtime
  rejection at `src/api/routes/web_call.py:31`.
- Filler words, which use `session.say()` (`src/core/agents/voice_features.py:346`).
  *Defaulted to reject, for the same reason as the greeting; say if you would rather ignore it.*

Runtime changes for duplex:
- The silence watchdog takes its existing `generate_reply` branch
  (`voice_features.py:188`), never the `say` branch.
- The session gets an explicit `inference.VAD(model="silero")` so the user can barge in.
- The Exotel greeting gate calls `turn_detection` updates, which are OpenAI-realtime specific
  (`session.py:1625`). Duplex skips that call.

## Steps

Each step stays green and can be reverted on its own. Run
`uv run python -m unittest discover -s tests` after every step.

- [x] **1. SDK bump.** Change `pyproject.toml:13` and `docker/requirements-agent.txt:7` to
  `~=1.8.8`, run `uv lock`/`uv sync`, and check that the new dependency floors (`openai>=3.19`,
  `websockets>=17.1,<17.2`, `onnxruntime>=1.30,<1.31`, OTel 1.45) resolve and that
  `docker/requirements-control.txt` does not conflict. Run the full test suite: the plugin-drift
  tests in `tests/test_speech_models.py` and `tests/test_realtime_capabilities.py` show any
  roster that moved. Behaviour change to watch: tools still running at the interruption timeout
  now continue asynchronously (1.8.7).
- [x] **2. GPT-6 in cascade.** Add `gpt-6-luna` and `gpt-6-sol` to `REASONING_MODELS`
  (`src/core/model_support/capabilities.py:40`), add their token rates to
  `src/core/pricing/rates.py` next to `gpt-5.6-*` (line 69) using OpenAI's pricing page, and
  update the comment block at `capabilities.py:36`. Tests: allowlist, knob gating (temperature
  rejected, effort and verbosity accepted, tool-compatible), and pricing.
- [x] **3. gpt-realtime-2.1 / -2.1-mini.** First, a realtime session probe. A scratch script
  opens a session with `session.truncation` and `semantic_vad` against each model. Only if both
  are accepted, add them to `REALTIME_GA_MODELS` (`capabilities.py:118`); otherwise they go in
  without truncation support. Add `_realtime` rates in `rates.py:75`. Tests:
  `test_realtime_capabilities`, `test_model_allowlist`, pricing.
- [x] **4. ElevenLabs v4.** Add `eleven_v4` and `eleven_v4_turbo` to `ELEVENLABS_TTS_MODELS`
  (`src/core/model_support/speech.py`) and to `_ELEVENLABS_NO_SPEED_MODELS`
  (`src/core/agents/tts/factory.py:28`), but only after a one-call check that `speed` is refused.
  The plugin routes both through text-to-dialogue, like v3. Add character rates in
  `rates.py:105`. Update the `ElevenLabsTTSConfig.model` description
  (`tts_config.py:81`). Tests: `test_speech_models` plugin-agreement, schema, pricing.
- [x] **5. Sarvam model field + bulbul:v4-flash.**
  - `speech.py`: add `SARVAM_TTS_MODELS = {"bulbul:v3", "bulbul:v4-flash"}` and
    `SARVAM_V4_FLASH_SPEAKERS` (the full roster, written out, because the API image has no
    plugin). Make `unsupported_sarvam_speaker_reason(speaker, model)` model-aware.
  - `SarvamTTSConfig`: add `model: Literal[...] = "bulbul:v3"`, raise `speaker` `max_length` to
    40, and add a `model_validator(mode="after")` that checks the speaker against that model's
    roster plus the v4 bounds (pace 0.5–2.0, temperature ≤ 1.0, sample rate in
    {8000, 16000, 22050, 24000}). The current bounds stay on the fields for v3.
  - `tts/factory.py`: replace the `SARVAM_TTS_MODEL` pin with `tts_config.get("model",
    "bulbul:v3")`, and pass that same model to `validate_sarvam_speaker`.
  - `validate_language`: allow the 11 IN22 codes for v4-flash only. *Default: allow them; Sarvam
    rejects them per subscription and the plugin falls back.* If that is wrong, drop this
    sub-step.
  - Add the `bulbul:v4-flash` rate in `rates.py:128`.
  - Tests: the roster equals the plugin's `MODEL_SPEAKER_COMPATIBILITY["bulbul:v4-flash"]` (in
    `test_speech_models`), v3 speakers are rejected on v4 and the reverse, bounds, and the
    default model is v3.
- [x] **6. Duplex: API side (expand).** Add `"duplex"` to `AssistantMode`
  (`llm_config.py:20`), the new fields, and a `mode == "duplex"` branch in
  `validate_mode_config` (`llm_config.py:168`). Add the greeting-audio, filler and text_only
  rejections, including `enforce_stored_mode_constraints` for PATCHes that change only one
  side. Gates 3 and 4: `unavailable_model_reason` for `gpt-live-1` and `backend_model`, and
  `rejected_config_reason` probes the **backend** model with its knobs and tool schemas. Pricing
  goes in `rates.py`: `gpt-live-1` per session second, read through the existing
  `llm_session_duration`. Tests: schemas, route, the cascade-config rule table extended with
  duplex rows.
- [x] **7. Duplex: worker side.** Add the `is_duplex` branch in `session.py` around line 876:
  `openai.realtime.GPTLiveModel(model=, voice=, delegation="responses",
  responses_options={model, instructions, reasoning, text, service_tier, tool_choice})`,
  `AgentSession(llm=..., vad=inference.VAD(model="silero"))`, the agent `instructions` as the
  voice persona, and tools unchanged (they go to the backend). Skip the realtime
  `turn_detection` toggles in the Exotel gate. In the greeting path, use `generate_reply` and
  log when the handle ends with `RealtimeError`. The silence watchdog is forced onto its LLM
  branch. Tests: `test_agent_entrypoint` duplex path (with a mocked GPTLiveModel), and
  `test_session_audio` if the gate code moves.
- [ ] **8. Manual verification (riskiest step, last).** One real web call and one real Exotel
  outbound call on a duplex assistant with one tool attached. Check: greeting on speaks_first,
  barge-in, tool round trip, end-of-call webhook, and `UsageRecord.llm_session_duration > 0`
  with a price. Then repeat one cascade call on `gpt-6-luna` and one pipeline call on
  `gpt-realtime-2.1`.
- [x] **9. Docs (same change set as each step, checked here).** Update `docs/reference/models.md`,
  `docs/reference/compatibility.md` (the duplex column plus its rejections),
  `docs/reference/troubleshooting.md` (a refused GPT-Live greeting, the 128-message history
  cap), `docs/architecture/cascade-pipeline.md` (GPT-6 knobs), `docs/api/assistant/{create,
  update,index,list}.md`, `README.md` and `docs/features.md` (the new mode), and the `CLAUDE.md`
  "Assistant modes" section plus the same block in `AGENTS.md`. Run
  `uv run mkdocs build --strict`, `uv run python scripts/check_mermaid.py`, and `uvx ruff check`
  on the touched paths.

## Delivery and rollback

- Order: step 1 alone, then steps 2–5, which only add list entries and are safe in either
  image. Steps 6–7 deploy **agent image first, API second**, so that no API ever accepts
  `duplex` while a worker still treats it as pipeline.
- Rollback for steps 2–5: revert the commit. Stored rows that hold a new model would then fail
  gate 1 on their next PATCH, and `scripts/audit_assistant_models.py --apply` clears them.
- Rollback for duplex: revert the API first, which stops new duplex rows. Existing duplex rows
  need a one-off `assistant_mode` reset to `realtime` with `gpt-realtime-1.5`. That script
  belongs in the step 6 PR and is read-only unless `--apply` is passed.
- Rollback for step 1: re-pin `~=1.8.2` and restore `uv.lock`.

## Verification

| Command | Expected |
|---|---|
| `uv run python scripts/check_model_allowlist.py` | exit 0, with the new ids no longer under "candidates" |
| `uv run python -m unittest discover -s tests` | all green; count goes up by the new tests |
| `uv run mkdocs build --strict` | clean |
| `uv run python scripts/check_mermaid.py` | exit 0 |
| `uvx ruff check <touched paths>` | no new findings |

## Risks

| Risk | Mitigation |
|---|---|
| GPT-Live refuses or delays the greeting on telephony, so the caller hears silence | Log it, then let the caller speak first. Manual Exotel test in step 8 before docs call duplex production-ready |
| v4-flash roster drifts in a later plugin release | The plugin-agreement test fails the suite, as it already does for v3 |
| Vendor prices for the new models are missing or wrong, so a call prices as zero | Every rate is read from the vendor page, and the URL and date go in a comment. `test_provider_pricing` asserts that every allowlisted model has a rate |
| 1.8.8 dependency floors clash with the control image's `openai` pin | Step 1 checks the lockfile and does nothing else |

## Progress log

- **Baseline (1.8.2):** `uv run python -m unittest discover -s tests`: 562 tests, OK.
- **Step 1 (done).** Pinned `~=1.8.8` in `pyproject.toml` and `docker/requirements-agent.txt`,
  then ran `uv lock` and `uv sync`. Resolved versions: livekit-agents and every plugin 1.8.8,
  openai 3.33.0, OpenTelemetry 1.45.1. `uv lock` also tried to move `mistralai` from 2.x to
  3.2.0, a major release the agent image does not run (that image pins v2.4.5). I pinned it
  with `mistralai>=2.1.3,<3`, which resolves to 2.10.1.
  The bump surfaced two drift failures, which is what those tests are for:
  - `test_the_vertex_only_set_matches_the_plugin`: since 1.8.5 the plugin's
    `KNOWN_VERTEXAI_MODELS` lists every model Vertex serves, `gemini-3.8-live` included. The
    test now compares against `KNOWN_VERTEXAI_MODELS - KNOWN_GEMINI_API_MODELS`. Our allowlist
    was already correct.
  - `TestTTSModelSetsMatchThePlugins.test_elevenlabs`: the v4 models. I pulled step 4 forward
    so that step 1 ends green.
- **Step 4 (done, pulled forward).** Added `eleven_v4` and `eleven_v4_turbo` to
  `ELEVENLABS_TTS_MODELS` and `_ELEVENLABS_NO_SPEED_MODELS`. The plugin source shows
  text-to-dialogue sends `stability` only (`_DIALOGUE_VOICE_SETTINGS_FIELDS`). **Correction,
  found in step 5:** that plugin path is not ours. `create_tts` sends every ElevenLabs model
  through our own HTTP client (`src/services/elevenlabs/v3_nonstream.py`,
  `POST /v1/text-to-speech/{voice}/stream`). So I re-checked with a live probe
  (`el_probe.py`) on that exact request. `eleven_v4` and `eleven_v4_turbo` both return 200
  with audio. `speed=1.2` is accepted but ignored: the output has the same byte length as
  with no settings, and v3 behaves the same way. Dropping `speed` for v4 therefore stays. Rates are $0.08 and $0.04 per 1K characters
  (elevenlabs.io/pricing/api, 2026-10-17). New tests: v4 speed drop, and every allowlisted
  OpenAI LLM and ElevenLabs TTS model has a rate. 565 tests, OK. Ruff on the touched files:
  28 findings before and 28 after, so nothing new.
- **Step 2 (done).** Added `gpt-6-luna` and `gpt-6-sol` to `REASONING_MODELS`, with the
  probe evidence in the comment. Rates are $0.10/$0.01/$0.50 and $2.00/$0.20/$10.00 per 1M
  tokens (developers.openai.com/api/docs/pricing, 2026-10-17). Tests: the schema accepts
  effort/verbosity/flex and rejects temperature; `create_llm` keeps effort and verbosity with
  tools and drops temperature; the plugin injects no reasoning. 569 tests, OK.
- **Step 3 (done).** Scratch probe `rt_probe.py` sent our exact `session.update` (truncation,
  semantic VAD, transcription, noise reduction) to `gpt-realtime-1.5` (control),
  `gpt-realtime-2.1` and `gpt-realtime-2.1-mini`, in audio and text output. All six
  combinations returned `session.updated` with the truncation applied. Added both models to
  `REALTIME_GA_MODELS`, which also gives them truncation, with rates. Tests: truncation
  support, pipeline acceptance, and the pricing-coverage test. 570 tests, OK.
- **Step 5 (done).** `SarvamTTSConfig.model` is a Literal of `bulbul:v3` (default) and
  `bulbul:v4-flash`. `speaker` is checked against the chosen model's roster, and its
  `max_length` went from 30 to 40. v4-only limits (pace 0.5–2.0, temperature ≤ 1.0, sample
  rate 8000/16000/22050/24000) are applied in a model validator. `speech.py` carries the full
  224-name roster, written out and asserted equal to the plugin's. A v3 name used on v4 gets
  the matching v4 names as suggestions (e.g. `shubh` lists `shubh_hi_customer`, …). In the
  factory the model comes from the config, and rows without one stay on v3.
  **Found while building:** since 1.8.6 the plugin's language Literal also includes the 11
  IN22 codes, so `validate_language("sarvam_tts", "as-IN")` passes for v3 too. Added
  `SARVAM_IN22_TTS_LANGUAGES` (`stt/lang.py`). On v3 those codes fall back to en-IN with an
  error log, and on v4-flash they pass through. The rate is INR 20 per 10K characters, the
  list price from Sarvam's v4-flash blog, because the pricing page does not list it yet. One
  of my own tests used a speaker that does not exist (`simran_enhi_banking`). The validator
  rejected it, as it should, and I corrected the test and the schema description.
  588 tests, OK. Ruff: no new findings after fixing one import order and two nested `with`
  blocks that I had introduced.
- **Step 6 (done).**
  - `capabilities.py`: `GPT_LIVE_MODELS`, `GPT_LIVE_VOICES` (plugin 1.8.8: beacon, cedar,
    cinder, marin, stone, vesper), `DUPLEX_BACKEND_MODELS = REASONING_MODELS`, and the
    defaults.
  - `llm_config.py`: `"duplex"` added to `AssistantMode`, plus `backend_model` and
    `backend_instructions` (rejected outside duplex). `validate_mode_config` gained
    `greeting_audio=` and `filler_words=` so the rule table stays in one place, and
    `_validate_duplex` judges the knobs against the backend model.
  - `assistant_guard.py`: duplex checks that both models are served and probes the backend.
    The stored-row guard passes the effective greeting and filler settings.
    `uses_responses_tools(mode)` makes duplex tool schemas strict, as in cascade.
  - Routes: a switch into or out of duplex starts from a clean `assistant_llm_config`, the
    same way leaving realtime already did. `text_only` web calls are refused for duplex.
  - Pricing: `ModelRate.session_second`; `gpt-live-1` costs $0.05/min, billed per second.
    `get_rate` falls back from a dated snapshot (`gpt-6-luna-2026-09-30`) to its alias,
    because GPT-Live reports the backend tokens under the snapshot name.
  - Tests: new `tests/test_duplex_mode.py` with 23 tests. A mutation check confirmed they
    bite: with the greeting rule and the duplex clearing disabled, 4 tests failed; after
    restoring, all pass. Full suite: 611 tests, OK. Ruff: the only new findings are two
    `UP045` on the new fields, which use `Optional[...]` to match every other field in that
    model.
- **Step 7 (done).** `create_gpt_live` (`src/core/agents/llm/factory.py`) builds
  `GPTLiveModel(delegation="responses")`. Its backend options are filtered by the same
  `unsupported_knob_reason` that `create_llm` uses, and when `backend_instructions` is unset
  a built-in default is used. In `session.py`, `is_duplex` and `speaks_own_audio` make
  duplex: build no TTS, use an explicit local Silero VAD (the session drops its default for
  a duplex model, and barge-in needs one), send strict tool schemas, route the silence
  watchdog through `generate_reply`, blank the caller at the Exotel gate (GPT-Live would
  otherwise answer the ring tone), skip any prerecorded greeting, and greet through
  `generate_reply`, logging when GPT-Live declines. The existing
  `isinstance(llm, realtime.RealtimeModel)` turn-detection toggles already skip it
  (`GPTLiveModel` is a `DuplexModel`). There is no `entrypoint()` harness, so I tested it in
  two layers:
  - 4 unit tests for `create_gpt_live` (27 in `test_duplex_mode.py`, 615 in the suite).
  - A live probe (`live_probe.py`) opened real GPT-Live sessions with the exact options
    `create_gpt_live` builds and one strict function tool. The `gpt-5.6-luna` backend and
    `gpt-6-luna` with effort `low` both got `session.started` and closed cleanly.
    `gpt-6-sol` with effort `minimal` was refused at session start with
    `responses_validation_failed`, which is the value API gate 4 rejects up front.
  Ruff's one new finding is `BLE001` on the catch-all in `create_gpt_live`, which mirrors
  `create_llm`'s identical guard (flagged the same way at `factory.py:139`).
- **Step 9 (done).** Updated `docs/reference/models.md`, which gains a new "GPT-Live" section,
  GPT-6 rows, the gpt-5.1/gpt-5.4-nano deprecation, the realtime 2.1 models, ElevenLabs v4,
  Sarvam `model`, the IN22 codes, and the full 224-speaker v4-flash table generated from the
  code set. Also updated: `docs/reference/compatibility.md` (a duplex column everywhere and a new
  "Duplex mode" section), `docs/reference/troubleshooting.md` (a duplex section),
  `docs/architecture/runtime-modes.md`, `docs/architecture/cascade-pipeline.md` (GPT-6),
  `docs/api/assistant/{create,update,index,list}.md` (a Duplex tab in create, a "Switch to
  Duplex" tab in update), `docs/features.md`, `README.md`, the "Assistant modes" section of
  `CLAUDE.md` (`AGENTS.md` has no such section), and `docs/changelog.md` with a 1.6.0 entry.
  `version.py` and `pyproject.toml` are bumped to 1.6.0, per the changelog's rule that a
  behaviour change gets a minor version.
  **Knock-on:** `tests/test_mcp_docs.py::test_search_finds_relevant_pages` failed. The new
  prose pushed `api/calls/queue-status.md` to 11th in a raw-term-count search. I widened the
  window from 10 to 12, the fix the test's own comment documents (see Out-of-scope
  observations). `uv run mkdocs build --strict` is clean; `check_mermaid.py`: 20 diagrams, 0
  broken.
- **Review pass.** `code-simplicity-reviewer` findings applied:
  - the lambda table in `create_gpt_live` became explicit `keep()` blocks;
  - `_require_served()` replaced the duplicated served-model check in the guard;
  - the route has one `replace_llm_config` condition;
  - the `DUPLEX_BACKEND_MODELS` alias is gone.

  Findings declined, with reasons:
  - `uses_responses_tools` stays as a named rule, used in three places.
  - The `SARVAM_TTS_MODEL` alias stays because tests import it.
  - The v4 speaker suggestion stays because it is what turns the error into a fix.

  615 tests, OK. Ruff over every touched file: three new findings, all deliberate (two
  `UP045` matching the model's style, one `BLE001` mirroring `create_llm`).
- **Correctness review** (a fresh-context reviewer subagent; 0 critical, 3 risks, 1
  question). All four were checked against the code and fixed:
  1. `InputGuardController` blanked the caller for `input_guard_window_sec` (default 3 s) at
     the start of every agent reply. For GPT-Live, which listens while it speaks, that deafens
     it exactly when a barge-in matters. The guard is now off in duplex.
  2. The Exotel pre-answer mute for duplex depended on `allow_interruptions`, but GPT-Live
     answers ring tone either way. Duplex now always mutes before answer.
  3. The duplex greeting did not set `agent_instance._allow_interruptions`, unlike the other
     modes. It now does.
  4. The dated-snapshot pricing fallback applied to every model. That would have priced
     `gpt-4o-2024-05-13` as `gpt-4o`, which has a different list price. It is now limited to
     `REASONING_MODELS`, the duplex backend candidates, and a test covers the old snapshot.

  616 tests, OK.
- **Step 8 (open, needs the user).** Real-call checks need the Exotel trunk and a web client;
  the checklist is in the report.

- **Follow-up (2026-10-17, user request).** Three changes after the review:
  1. ElevenLabs TTS rates in `src/core/pricing/rates.py` set to the current list
     (elevenlabs.io/pricing/api, re-fetched 2026-10-17): v4, v3 and multilingual v2 at $0.08
     per 1K characters; v4 turbo, v3 conversational, turbo and flash at $0.04. The two v1
     models are no longer listed and keep $0.10.
  2. `gpt-5.1` and `gpt-5.4-nano` removed from `REASONING_MODELS`,
     `REASONING_TOOL_INCOMPATIBLE` and `PLUGIN_INJECTS_REASONING`
     (`src/core/model_support/capabilities.py`). Their rates stay, so usage recorded before the
     change still prices.
  3. New `scripts/migrate_retired_models.py` (dry run by default, `--apply` writes). It moves
     `gpt-5.1` to `gpt-6-sol` and `gpt-5.4-nano` to `gpt-6-luna`, the replacements LiveKit
     names, in `assistant_llm_config.model` and `.backend_model`. Tested by
     `tests/test_migrate_retired_models.py`. Docs: changelog (now a breaking change),
     models.md, compatibility.md, troubleshooting.md, CLAUDE.md.

  621 tests OK; allowlist check clean; strict docs build clean; 20 diagrams OK.
- **Second review round (2026-10-17).** Fixed from a full-diff correctness review:
  `max_output_tokens` now `ge=16` (OpenAI's floor; the save-time probe always sends 16, so a
  smaller stored value was never checked); an IN22 language on `bulbul:v3` is a 422
  (`SARVAM_V4_FLASH_ONLY_LANGUAGES` in `speech.py`, parity-tested against the plugin; the set
  is 12 codes, not 11 as first written); the migration turns `reasoning_effort: "minimal"`
  into `"none"`; dated snapshots of the two retired models still price. Docs: new
  `docs/architecture/duplex-mode.md` and `docs/reference/pricing.md` (test-guarded), dated
  release table in the changelog, OpenAI and Gemini realtime voice lists in models.md, and
  stale lines fixed in troubleshooting, models, CLAUDE.md, AGENTS.md (new 1.6.0 entry) and
  README. Not changed: with `speaks_first` off, an outbound Exotel duplex call is not muted
  during the ring tone (cascade has the same shape).

  626 tests OK; strict docs build clean; 21 diagrams OK.

## Out-of-scope observations

- The allowlist check now also lists `gpt-6-astra` and `gpt-6.1-sol` as served but not
  allowlisted. Not added; they need the same probes GPT-6 got.
- `src/api/mcp_docs.py::search_docs` ranks by raw term count, so a long page that repeats a
  common word outranks the short page that answers the query. Each docs addition can push a
  relevant page out of the test window again. A length-normalised score would fix it.
- Text-to-dialogue (v3/v4) also drops `similarity_boost`, `style` and `use_speaker_boost`,
  and the plugin logs a warning when they are set. Our schema description says voice
  settings "apply to all models". Not changed.
