# Progress — 2026-10-21-feature-duplex-pricing-gemini-knobs

Approved by the user ("approved") on 2026-10-21.

1. D-01: `rates.py` SERVICE_TIER_MULTIPLIER; `calculator.py` `_tier_multiplier` replaces the tier-to-unpriced guard. Per-second rates and Realtime-API models excluded. 4 tests in test_duplex_mode.py.
2. D-02: `session.py` logs a WARNING naming unpriced provider/model at the final persist.
3. D-03: `calculator.duplex_cost_split`, exported from `core/pricing`; used by the webhook (`livekit_svc.py`, duplex only) and a `Duplex cost` log line. 3 unit tests + 1 webhook test, and a cascade negative assertion.
4. G-01: `GEMINI_UNREAD_KNOBS` in `llm_config.py`; `session.py` forwards temperature and max_output_tokens only when set. 3 tests, including that the installed plugin accepts both kwargs.
5. G-05: comment in capabilities.py now says 1.8.8.
6. Docs: usage-accounting, pricing, compatibility, assistant index/update, calls/webhook, changelog (Unreleased), dev-docs usage-and-pricing, ADR 0007 + README row.
7. Verify: 681 tests OK (was 670); mkdocs strict builds; mermaid 39 diagrams 0 broken; ruff clean on new lines (remaining findings pre-existing).

## Deviations
- The plan said to run `scripts/audit_assistant_models.py` to find stored Gemini rows holding a refused knob. That script checks model ids, not knobs, so it cannot find them and I did not touch the database. Affected rows surface as a 422 on their next update; the changelog says so.
- No version bump; the changelog entry is under "Unreleased" for the user to version.

## Out-of-scope observations
- OpenAI `realtime` and `pipeline` still store and ignore the Responses knobs (schema comment says "harmless"). Same silent no-op as G-01; offer as a follow-up.
- The full suite prints an `AssertionError` from `livekit/rtc/_ffi_client.py` dispose at interpreter exit in about 1 run in 3, with and without these changes. Pre-existing.
- G-02 thinking tokens, G-03 greeting private call, G-04 extended-thinking with tools: still open, need a live Gemini call.

## Follow-up, same day (user asked)
- Ran `scripts/audit_assistant_models.py --no-network` (dry run, read-only): 1 of 140 assistants flagged, a duplex assistant with model `gpt-live-1`. False positive: `expected_models` has no duplex branch, so it judges `gpt-live-1` against the realtime list and its fallback `gpt-realtime-1.5` is wrong. `--apply` would break that assistant. Not applied, not fixed (out of scope).
- Read-only query of `assistants`: 45 Gemini realtime assistants, none hold a refused knob, so the new 422 affects no stored row.
- Observation: the script prints the MongoDB URL with its username and password in clear text; the stored password is `12345`.
- Version bumped 1.6.0 → 1.7.0: `pyproject.toml`, `uv.lock`, `src/core/version.py`, `docs/api/health.md`, `docs/api/mcp.md`; changelog "Unreleased" became 1.7.0 (2026-10-21) with a table row. 681 tests OK, mkdocs strict builds.
