# 0005. Move to livekit-agents 1.8.2 and make Gemini 3.8 Live the default

- **Status:** Accepted
- **Date:** 2026-09

## Context

`livekit-agents` 1.8.2 shipped two new Gemini Live models and fixed a plugin bug that we had been
working around ourselves. The same audit turned up two models we accepted but could not run:

- a Vertex-only Gemini model that the plugin refuses to build without `vertexai=True`;
- Deepgram tiers that Deepgram no longer prices, while this platform prices every call it accepts.

## Decision

`livekit-agents` is pinned to `~=1.8.2` (was `~=1.7.1`), in `pyproject.toml` **and**
`docker/requirements-agent.txt`. Three things follow from the bump:

1. **Two new Live models are allowlisted**, taken straight from the 1.8.2 plugin Literal:
   `gemini-3.8-live` and `gemini-3.8-live-extended-thinking`. `GEMINI_LIVE_MODELS` is checked
   against that Literal by a parity test, so a plugin bump that adds a model fails the suite until
   the allowlist follows.
2. **The Gemini default is now `gemini-3.8-live`** (was
   `gemini-2.5-flash-native-audio-preview-12-2025`). Assistants that omit `model` move with it.
   Extended-thinking is selectable and reasons before speaking: slower first word, async-only
   function calling. Nothing rejects it.
3. **The 3.1 mid-session guard is gone.** `GEMINI_NO_MIDSESSION_CONTENT_MODELS` and the warning in
   `src/core/agents/session.py` documented a **plugin** bug that `livekit-plugins-google` 1.8.2
   fixes upstream: `generate_reply()`, `update_instructions()` and `update_chat_ctx()` now work on
   every Live model.

Two rules came out of the same audit:

4. **`gemini-live-2.5-flash-native-audio` is refused at the API** (`GEMINI_VERTEX_ONLY_MODELS`).
   It is in the plugin's Literal, but the plugin raises while building the model unless
   `vertexai=True`, which this deployment never sets. When it was accepted, it gave a call that
   connected and then lost its worker.
5. **The Deepgram STT allowlist is a deliberate subset**, not plugin parity: the `nova-3` line plus
   the two `flux` models. Deepgram stopped publishing a price for `nova-2`, `enhanced`, `base` and
   hosted `whisper`. `tests/test_speech_models.py` asserts subset-of-plugin **and** that every
   accepted id has a rate.

Pricing gained `GEMINI_LIVE_RATES`, `CARTESIA_TTS_RATES`, `CARTESIA_STT_RATES` and
`MISTRAL_TTS_RATES` in `src/core/pricing/rates.py`, so every provider this platform runs is priced.

- Gemini is keyed under `gemini`, which is what the plugin reports for an API-key session once
  `normalize_provider` lowercases it.
- Two numbers are weaker than the rest and say so beside themselves:
  - Cartesia is **derived** from its plan tiers; Cartesia quotes no per-unit price.
  - Deepgram is priced at its **regular** rate while its page shows a promotional one.

Open questions from this work:
[`agent-tracking/plans/2026-09-21-feature-gemini-3.8-live/open-questions.md`](../../agent-tracking/plans/2026-09-21-feature-gemini-3.8-live/open-questions.md).

## Consequences

- **Do not reintroduce** `GEMINI_NO_MIDSESSION_CONTENT_MODELS` or the warning. The remedy for the
  old symptom is the version pin; `docs/reference/troubleshooting.md` keeps the symptom documented
  that way.
- **Do not re-add a Deepgram id without a price.** An accepted model with no rate bills as zero.
- The pin has since moved to `~=1.8.8` ([0006](0006-duplex-mode-gpt-6-and-new-speech-models.md)).
- Where the code differs from the original wording: AGENTS.md says `GEMINI_LIVE_MODELS` keeps the
  Vertex-only id for parity. In the current code it does not. `GEMINI_LIVE_MODELS` holds four ids
  (`gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.1-flash-live-preview`,
  `gemini-2.5-flash-native-audio-preview-12-2025`), `GEMINI_VERTEX_ONLY_MODELS` holds the fifth,
  and the parity tests assert that the two sets together equal the plugin's Literal.

## Where in the code

| What | File | Symbol |
|---|---|---|
| Gemini model sets and default | `src/core/model_support/capabilities.py` | `GEMINI_LIVE_MODELS`, `GEMINI_VERTEX_ONLY_MODELS`, `DEFAULT_GEMINI_LIVE_MODEL` |
| Vertex-only refusal | `src/api/models/api_schemas/config/llm_config.py` | `validate_mode_config` (realtime branch) |
| Plugin parity tests | `tests/test_realtime_capabilities.py` | `test_the_allowlist_accounts_for_every_model_the_plugin_lists`, `test_the_vertex_only_set_matches_the_plugin` |
| Deepgram subset + rate tests | `tests/test_speech_models.py` | `test_deepgram_is_a_subset_of_the_plugin_with_nothing_invented`, `test_every_allowlisted_deepgram_model_has_a_rate` |
| Deepgram allowlist | `src/core/model_support/speech.py` | `DEEPGRAM_STT_MODELS` |
| Rates | `src/core/pricing/rates.py` | `GEMINI_LIVE_RATES`, `CARTESIA_TTS_RATES`, `CARTESIA_STT_RATES`, `MISTRAL_TTS_RATES`, `get_rate` |
| Provider spelling | `src/core/agents/usage.py` | `normalize_provider` |
