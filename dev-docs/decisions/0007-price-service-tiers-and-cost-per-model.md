# 0007. Price service tiers and report cost the same way in every mode

- **Status:** Accepted
- **Date:** 2026-10

## Context

An audit of duplex mode and Gemini Live (`agent-tracking/reports/2026-10-21-audit-duplex-gemini-pricing.html`)
found that a non-default OpenAI `service_tier` left every OpenAI LLM entry unpriced. In duplex the
tier belongs to the backend model, yet the GPT-Live voice entry, billed per second, was zeroed too.
The webhook also showed one total, so the backend model's share was invisible. Gemini realtime
stored `reasoning_effort`, `verbosity`, `service_tier`, `tool_choice` and `parallel_tool_calls` and
sent none of them.

## Decision

1. `service_tier` scales a token rate: flex 0.5, fast and priority 2 (OpenAI pricing page,
   2026-10-21). Per-second rates are never scaled. Realtime-API models and unknown tiers stay unpriced
   rather than guessed.
2. Cost is reported one way for every mode: the priced `model_usage` entries, summed into
   `estimated_cost_usd`. Duplex is not a special case, so it has no cost fields of its own; its
   backend model is simply the second entry, typed `backend_llm_usage` next to GPT-Live's
   `voice_llm_usage` the way cascade's parts are `llm_usage`, `stt_usage` and `tts_usage`. The relabel
   is applied after pricing and totalling, which key on `llm_usage`; the analytics sums accept all three. The worker logs one `Cost by model` line per call.
3. Gemini realtime refuses the five knobs it cannot read (`GEMINI_UNREAD_KNOBS`) and forwards
   `temperature` and `max_output_tokens`.

## Consequences

Do not scale a `session_second` rate by tier. Re-check `SERVICE_TIER_MULTIPLIER` whenever OpenAI
changes tier pricing. An assistant that already stores a refused Gemini knob gets a `422` on its next
update. Thinking tokens on `gemini-3.8-live-extended-thinking` are still not reported by the plugin, so
that estimate stays low.

## Where in the code

| What | File | Symbol |
|---|---|---|
| Tier multipliers | `src/core/pricing/rates.py` | `SERVICE_TIER_MULTIPLIER` |
| Tier rule | `src/core/pricing/calculator.py` | `_tier_multiplier` |
| Duplex type labels | `src/core/agents/usage.py` | `label_duplex_usage` |
| Analytics LLM types | `src/core/db/usage_aggregations.py` | `_LLM_TYPES` |
| Cost per model log line | `src/core/agents/session.py` | `Cost by model` |
| Gemini knob rule | `src/api/models/api_schemas/config/llm_config.py` | `GEMINI_UNREAD_KNOBS` |
| Gemini knob forwarding | `src/core/agents/session.py` | `gemini_knobs` |
