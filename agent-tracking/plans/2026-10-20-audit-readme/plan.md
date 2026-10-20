# Review plan — 2026-10-20-audit-readme

**Goal:** judge whether `README.md` is accurate, and whether it is overloaded with content that belongs in `docs/`.

The user accepted the proposed defaults (README only, standard depth, findings plus a slim outline, internal audience, HTML report). Those defaults fully define this review plan, so it was executed without a separate approval round; nothing in the repository is changed by it.

- [x] Read `README.md` end to end; measure lines per section.
- [x] Check the environment table against `src/core/config.py`, the Exotel bridge modules and `.env.example`.
- [x] Check the endpoint table against every `@router` decorator and the prefixes in `src/api/server.py`.
- [x] Check every path and relative link in the README exists; check the structure tree against `src/`.
- [x] Spot-check numeric and behavioural claims (dispatcher polling, retries, defaults, prices).
- [x] Map each README section to the `docs/` page(s) that already cover it.
- [x] Compare against the README standard (`core-be-structure-service/references/readme-standard.md`).
- [x] Write the report to `agent-tracking/reports/2026-10-20-audit-readme.html`.
