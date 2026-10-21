# Research — duplex backend pricing and Gemini Live

## Baseline
- 670 tests pass. Ruff on the audited paths: 7 findings, pre-existing.

## Duplex usage path (verified by simulation)
GPT-Live emits two usage streams (livekit/agents/llm/_realtime/gpt_live.py:917-940 and 993-1015): backend tokens as `LLMMetrics`
under `response.model` with provider = netloc of base_url (`api.openai.com`), and voice seconds as `RealtimeModelMetrics.session_duration`
under `gpt-live-1`. `ModelUsageCollector` keeps them as two `llm_usage` entries. With default tier, `price_model_usage` priced
`gpt-6-luna-2026-10-01` at $0.000152 and `gpt-live-1` 120 s at $0.10: the sum is the stored `estimated_cost_usd`.

## Duplex pricing failures reproduced
| Case | Result |
|---|---|
| `service_tier` fast / flex / priority | both entries unpriced, cost 0, pricing_complete False |
| backend model name `gpt-6-luna-20261001` or `...-2026-10-01-preview` | unpriced |
| `gpt-6-sol-2026-10-01` | priced |

## Gemini
- Plugin `_handle_usage_metadata` reports `response_token_count` as output; `thoughts_token_count` and `tool_use_prompt_token_count` exist on google-genai UsageMetadata (2.31.0) but are never read.
- Realtime mode accepts temperature, max_output_tokens, reasoning_effort, verbosity, service_tier, tool_choice for provider gemini (probe), none forwarded (session.py:870-877).
- Model ids equal the plugin's LiveAPIModels. Voices and the 3.8 thinking rule match the LiveKit docs.

## External facts (fetched 2026-10-21)
- OpenAI pricing page: gpt-live-1 $0.05/min per second; gpt-6-luna 0.10/0.01/0.50; gpt-6-sol 2.00/0.20/10.00; flex = 0.5x, fast (priority) = 2x.
- Google pricing page: 3.x Live text in 0.75, audio in 3.00, image 1.00, text out 4.50, audio out 12.00; output "including thinking tokens"; no cache price. 2.5 native audio 0.50/3.00/2.00/12.00.
- LiveKit docs: GPT-Live responses_options keys; service_tier literal listed as auto/default/flex/priority; gemini-3.8-live thinking not configurable, extended-thinking takes thinking_level low/medium/high.
