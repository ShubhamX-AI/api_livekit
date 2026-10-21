# Plan — 2026-10-21-feature-duplex-pricing-gemini-knobs

Goal: duplex cost is correct under a service tier and shown per component; Gemini realtime stops accepting settings it ignores.

Skills: core-be-build-feature, core-be-write-tests.

## Steps
- [x] 1. D-01 tier-aware pricing. `rates.py`: `SERVICE_TIER_MULTIPLIER = {"flex": 0.5, "fast": 2, "priority": 2}`. `calculator.py`: replace the `rate = None` guard with a multiplier on OpenAI token-priced entries; entries with `session_second` (gpt-live) never multiplied. Cascade/pipeline unchanged in outcome except now priced, not unpriced. Tests in tests/test_provider_pricing.py and test_duplex_mode.py.
- [x] 2. D-02 warning. `session.py` persist: log WARNING naming each model in `unpriced_model_usage`.
- [x] 3. D-03 cost split. `usage.py` or `pricing/`: helper deriving `estimated_cost_voice_usd` and `estimated_cost_backend_usd` from `model_usage` (duplex only, else None). Add to webhook `usage` block (`livekit_svc.py`) and the "Usage persisted" log line. Additive fields. Test.
- [x] 4. G-01 Gemini guard. `llm_config.py` realtime/gemini branch: 422 for reasoning_effort, verbosity, service_tier, tool_choice, parallel_tool_calls. `session.py`: forward temperature, max_output_tokens to `google_realtime.RealtimeModel` only when set. Tests in the realtime config test file.
- [x] 5. G-05 fix stale comment in capabilities.py.
- [x] 6. Docs: docs/reference/{usage-accounting,pricing,compatibility,models}.md, docs/concepts (realtime, duplex), docs/api/assistant/{create,update}.md, dev-docs subsystem page, add a dev-docs/decisions record for tier pricing.
- [x] 7. Verify and report.

## Files
src/core/pricing/{rates,calculator}.py, src/core/agents/session.py, src/services/livekit/livekit_svc.py, src/api/models/api_schemas/config/llm_config.py, src/core/model_support/capabilities.py, tests/, docs/, dev-docs/.

## Risks and rollback
- Existing stored duplex/cascade rows with a tier change from unpriced to priced: intended. Roll back by reverting the commit; no data migration.
- Rejecting Gemini knobs: a stored realtime/gemini row holding one of them would 422 on its next PATCH. Mitigation: `enforce_stored_mode_constraints` checks the merged row, so run `scripts/audit_assistant_models.py` first (dry run, read only) to list affected rows.
- Webhook gains fields only; no field removed.

## Verification
`uv run python -m unittest discover -s tests` (expect all pass plus new), `uvx ruff check <touched>`, `uv run mkdocs build --strict`, `uv run python scripts/check_mermaid.py`.
