# 08 — MCP docs search ranking, and ElevenLabs voice settings per model

## Request

> Fix these then "Two small known limits stay as they are: Docs search ranking. The docs search
> behind the /mcp endpoint can push the right page down as more pages are added. It needs a better
> scoring rule. ElevenLabs voice settings on v3/v4. The plugin's dialogue path for v3/v4 ignores
> similarity_boost, style and use_speaker_boost, but the field description says the voice settings
> apply to all models." and mcp should work perfectly

## Baseline (2026-10-17, through the real MCP streamable-HTTP handler)

- `initialize` and `tools/list` work: server `livekit-api-docs` 1.6.0, tools `list_docs`,
  `get_doc`, `search_docs`.
- `search_docs("outbound call queue status", limit=5)` does not return `api/calls/queue-status.md`.
- `search_docs("duplex gpt-live how it works")` does not return `architecture/duplex-mode.md`.
- `get_doc("changelog.md")` answers "No page", although the server's `instructions` tell agents to
  use `changelog.md` for release context. The page is excluded from the whole index
  (`src/api/mcp_docs.py::_NOT_REFERENCE`), not only from search.
- Cause of the ranking problem: `search_docs` scores by raw substring counts
  (`haystack.count(term)`), so long pages win and `call` also matches `callback`, `called`, ….

## ElevenLabs facts

Our ElevenLabs path is not the plugin's: `src/services/elevenlabs/v3_nonstream.py` posts to
`/v1/text-to-speech/{voice}/stream`. What the API honours per model, from
https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech (fetched 2026-10-17):

- Eleven v3: "Speed is not available", "Similarity is not available", "Speaker Boost is not
  available". Stability and style are not ruled out.
- Eleven v4 / v4 Turbo: "Both variants use two voice settings: Stability and Similarity." "Style
  and Speed sliders are not available." Speaker boost is not mentioned.

## Decisions

- Same rule as `speed` already follows: the API keeps accepting the field, the factory drops it
  for a model that does not read it and logs one warning. Rejecting it would make existing
  assistants that store these settings un-editable.
- Only settings ElevenLabs states are unavailable are dropped. `style` on v3 and
  `use_speaker_boost` on v4 stay, since the docs do not rule them out.
- `eleven_v3_conversational` is treated as v3, as the speed rule already does.
- Search: BM25 over whole words (simple plural folding), with title and path boosted. The changelog
  is indexed again, so `get_doc`/`list_docs` reach it; BM25's length normalisation is what keeps
  a long page from winning every query, which is the reason it was excluded.

## Steps

- [x] 1. BM25 ranking in `search_docs`; index the changelog again.
- [x] 2. Tests: ranking for known queries within the default limit, changelog reachable, and a
      test through the real streamable-HTTP handler (initialize, tools/list, tools/call).
- [x] 3. ElevenLabs: per-model unsupported settings in `src/core/agents/tts/factory.py`, dropped
      with one warning; tests.
- [x] 4. Docs: schema field descriptions, models.md, create.md, features.md, mcp.md.
- [x] 5. Gates: full tests, ruff on touched files, strict docs build, MCP smoke script.

## Rollback

Revert the commit. No data or config changes.

## Progress log

- **Steps 1–2.** `search_docs` (`src/api/mcp_docs.py`) ranks with BM25 over whole words
  (`_words`: lowercase, trailing plural `s` folded) plus a title/path boost. Constants were
  picked on 26 sample questions (scratch `eval.py`): binary title boost 2.0, `b=0.5`, `k1=1.2`
  gave the right page first for 22 and in the top three for 25. The raw-count scorer it
  replaced got 18 in the top three (MRR 0.48 → 0.91). The production function was re-checked
  against the same 26 questions: 22 / 25. `changelog.md` is indexed again; BM25's length
  discount keeps it from winning unrelated queries. Tests: 10 ranking cases at `limit=3`,
  plural folding, changelog reachable, and `TestMcpOverHttp` (initialize, tools/list,
  tools/call search_docs, and the traversal refusal) through the real streamable-HTTP handler.
- **Step 3.** `ELEVENLABS_UNREAD_SETTINGS` in `src/core/agents/tts/factory.py` replaces
  `_ELEVENLABS_NO_SPEED_MODELS`. v3 drops `similarity_boost`, `speed`, `use_speaker_boost`; v4
  drops `style`, `speed`. One warning lists what was dropped. `VoiceSettings.similarity_boost`
  is optional so v3 is no longer sent the 0.5 default. The old comment claimed our path goes
  through the plugin's text-to-dialogue; it does not (`v3_nonstream.py` posts to `/stream`), so
  the comment was rewritten from ElevenLabs' own model notes. One existing test pinned
  `eleven_multilingual_v2` to keep checking the 0.5 default on a model that reads it.
- **Step 4.** Docs: per-model table in models.md, create.md, features.md, mcp.md, the schema
  descriptions, and the 1.6.0 changelog.
- **Step 5.** 639 tests OK (after the review fixes: empty-index guard, `limit` header, `.md` no longer a title word); ruff counts unchanged on every touched file; strict docs build
  clean; 21 diagrams OK.
- **Follow-up: `style` and speaker boost confirmed (2026-10-17).** A byte comparison of audio
  with one setting flipped was inconclusive: ElevenLabs output differs between two identical
  requests even with a fixed `seed`. ElevenLabs' own `GET /v1/models` settles it instead: it
  reports `can_use_style` and `can_use_speaker_boost` per model. Only `eleven_multilingual_v2`
  has both; `eleven_v3_conversational` has speaker boost only; v3, v4, v4 turbo and every
  turbo/flash model have neither. `ELEVENLABS_UNREAD_SETTINGS` now follows those flags, so it
  covers the turbo and flash models too (they had been sent `style` and `use_speaker_boost`).
  `speed` and `similarity_boost` have no flag and still come from the model notes. Table-driven
  test `test_each_model_keeps_only_the_settings_it_reads`; docs table, create.md, schema text
  and changelog updated. 637 tests OK.
- **Follow-up: ignored settings are now refused (2026-10-17, user request: "those settings
  should not be acceptable … misleading").** Supersedes the drop-and-accept decision above.
  - `ELEVENLABS_UNREAD_SETTINGS` moved to `src/core/model_support/speech.py` (the API image
    needs it). `ElevenLabsTTSConfig._settings_fit_the_model` answers 422 naming the setting and
    the models that read it. Unset (null) settings never count, so a resent config with nulls
    passes.
  - Sarvam `temperature` on `bulbul:v4-flash` is a 422 (Sarvam fixes it at 0.6). Its schema
    default is now None instead of 0.3, so v4-flash rows never store a value they would then
    refuse on resend; the factory still uses 0.3 for v3 when it is unset.
  - Found while probing: ElevenLabs retired `eleven_monolingual_v1` and `eleven_multilingual_v1`
    (400 `unsupported_model`), though the plugin still lists them. Removed from
    `ELEVENLABS_TTS_MODELS` (`ELEVENLABS_RETIRED_TTS_MODELS`); the plugin-parity test accounts
    for them.
  - `scripts/migrate_tts_settings.py` (dry run by default) moves v1 rows to
    `eleven_multilingual_v2` and removes ignored settings from stored rows. The factory keeps
    dropping them at call time for rows not yet migrated.
  - Docs: models.md, create.md, troubleshooting.md, pricing.md, changelog, AGENTS.md. Note:
    CLAUDE.md is now a single `@AGENTS.md` line with its content moved into AGENTS.md; that
    change was not made in this task and was left as found.
  - 646 tests OK; strict docs build clean; 21 diagrams OK; one extra UP045 in tts_config.py
    from an `Optional[float]` matching every other field there.
