# Scope — 2026-10-21-feature-duplex-pricing-gemini-knobs

- **Type:** feature (fix from audit 2026-10-21-audit-duplex-gemini-pricing)
- **Requested by:** Shubham Halder
- **Date:** 2026-10-21

## Original request (verbatim)

> yes go for it

(in reply to: "Suggested fix order: D-01, then G-01, then D-03. Say which to start, and I will plan each as a separate task.")

## Agreed scope

| Question | Answer |
|----------|--------|
| Target | Audit findings D-01, G-01, D-03 (default: also D-02 warning, G-05 comment) |
| Depth | standard |
| Out of scope | G-02 thinking tokens, G-03 greeting, G-04 live checks (need a live call); pipeline/cascade behaviour |
| Constraints | no new dependencies, no DB migration, webhook change additive only, no git commit |
| Success criteria | duplex + flex/fast/priority prices both entries; Gemini realtime 422s OpenAI-only knobs and forwards temperature/max_output_tokens; webhook and log show voice and backend cost; tests, docs, ruff, mkdocs strict green |
| Report format | HTML, all severities |

## Assumptions to confirm

- Tier multipliers: flex 0.5, fast and priority 2.0, applied to the backend entry only (OpenAI page 2026-10-21).
- Gemini knobs: reject reasoning_effort, verbosity, service_tier, tool_choice, parallel_tool_calls with 422; forward temperature and max_output_tokens. No thinking_level yet (unverified live).

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| Start order D-01, G-01, D-03 | "yes go for it" |
