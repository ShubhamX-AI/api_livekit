# Progress — 2026-10-20-audit-readme

- 2026-10-20: Scope recorded; user answered "defaults". Pack already registered in `AGENTS.md` (markers present) and `CLAUDE.md` (`@AGENTS.md`), no change.
- 2026-10-20: Environment table: all 64 variables in the README exist in code and match `.env.example` exactly; defaults spot-checked against `src/core/config.py`. Only `RTP_PORT_START`/`RTP_PORT_END` are read but not listed as rows (they are mentioned as fallbacks), which is acceptable.
- 2026-10-20: Endpoint table: matches all 50 routes in `src/api/routes/` with the prefixes from `src/api/server.py:161-178`.
- 2026-10-20: All README paths and relative links exist; the structure tree matches `src/` at the file level.
- 2026-10-20: Stale claims found: dispatcher polling (README.md:119), "all three" scripts (README.md:91), `mkdocs` commands without `uv run` (README.md:455,461), meeting-connector status note (README.md:191-194).
- 2026-10-20: Report written.

## Out-of-scope observations

- `docs/getting-started/index.md:29-50` still says assistants support "three execution modes" and omits `duplex`. This is the drift the duplicated README content invites.
