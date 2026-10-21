# Review plan — 2026-10-21-audit-duplex-gemini-pricing

Goal: answer the user's questions on duplex settings, backend-model pricing and Gemini Live, report-only.
Approval: user said "yes go on with the defaults" after the scope questions (2026-10-21).

Files, in review order: src/core/agents/llm/factory.py, src/core/agents/usage.py, src/core/pricing/{rates,calculator}.py,
src/core/agents/session.py (usage persist 470-585, Gemini build 870-885, greeting 1735-1765),
src/services/livekit/livekit_svc.py (end-call webhook 440-540), src/api/models/api_schemas/config/llm_config.py,
src/core/model_support/capabilities.py. Checklists: bugs, structure, tests, AI-generated-code (invented APIs).

Steps
- [x] Automated pass (unittest, ruff)
- [x] Read the installed SDK/plugin source for GPT-Live and Gemini usage reporting
- [x] Compare options against the LiveKit docs MCP pages (gpt-live, gemini)
- [x] Simulate usage folding + pricing offline (no DB, no live calls)
- [x] Check rates against the Google and OpenAI public pricing pages
- [x] Write report
