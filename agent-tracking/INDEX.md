# Agent Tracking Index

One row per task. Newest at the bottom. Keep status current at every phase change.

Status: `scoping` · `researching` · `awaiting-approval` · `approved` · `in-progress` · `done` · `blocked` · `cancelled`

| Date | Slug | Type | Status | Summary | Report |
|------|------|------|--------|---------|--------|
| 2026-09-05 | 2026-09-05-feature-usage-accounting | feature | done | Per-call token and usage accounting on `UsageRecord`, every mode | — |
| 2026-09-18 | 2026-09-18-feature-meet-connector-service | feature | done | Plan 01: the meeting connector service; research: putting a voice agent into Google Meet | — |
| 2026-09-18 | 2026-09-18-feature-meet-api-integration | feature | done | Plan 02: meeting-call changes inside `api_livekit` (superseded in part by plan 03) | — |
| 2026-09-18 | 2026-09-18-feature-meet-worker-dispatch | feature | done | Plan 03: dispatch the connector as a LiveKit worker (connector-repo half still open) | — |
| 2026-09-19 | 2026-09-19-debug-meeting-call-audio | debug | done | Plan 04: Google Meet calls connect but no audio moves; resolved 2026-09-20 | — |
| 2026-09-21 | 2026-09-21-feature-gemini-3.8-live | feature | done | Plan 05: Gemini 3.8 Live models; open questions in `open-questions.md` (was 06) | — |
| 2026-10-17 | 2026-10-17-feature-livekit-1.8.8-models | feature | in-progress | Plan 07: livekit-agents 1.8.8, GPT-6, duplex, new speech models; manual calls open | [report](reports/2026-10-17-feature-livekit-1.8.8-models.html) |
| 2026-10-17 | 2026-10-17-feature-mcp-search-elevenlabs-settings | feature | done | Plan 08: MCP docs search ranking, ElevenLabs voice settings per model | [report](reports/2026-10-17-feature-mcp-search-elevenlabs-settings.html) |
| 2026-10-17 | 2026-10-17-audit-logging-traceability | audit | done | Logging audit: 28 findings (9 High); bridge logs lost, no request tracing, secrets in logs | [report](reports/2026-10-17-audit-logging-traceability.html) |
| 2026-10-20 | 2026-10-20-debug-logging-p1-fixes | debug | done | Fixed the six P1 logging findings (L-01, L-02, L-03, L-05, L-06, L-09); 22 new tests, 668 OK | [report](reports/2026-10-20-debug-logging-p1-fixes.html) |
