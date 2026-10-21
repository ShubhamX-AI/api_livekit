# User Tokens By Model

`GET /analytics/tokens/by-model` returns one row per `(type, provider, model)` for the
authenticated user's calls. Rows include numeric usage totals, estimated AI-provider cost, and
`total_records`. `type` is `llm_usage`, `stt_usage` or `tts_usage`; for a `duplex` call the two language
models come back as `voice_llm_usage` (GPT-Live) and `backend_llm_usage` (the backend model), and the
LLM token totals include both. Duplex calls recorded before 1.7.0 show `llm_usage`.

```bash
curl "https://api-livekit-vyom.indusnettechnologies.com/analytics/tokens/by-model" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Optional `start_date` and `end_date` filters default to the last 30 days. Provider values use
the schema-version 3 normalization rule.

`total_estimated_cost_usd` sums entry-level estimates, preserving attribution when a call
switches models. It excludes unpriced entries and non-AI platform costs.
