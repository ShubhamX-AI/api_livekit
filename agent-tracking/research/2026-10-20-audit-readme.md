# Research — 2026-10-20-audit-readme

## Size

`README.md` is 762 lines in 24 `##` sections. The largest are Project Structure (132 lines, README.md:594-725), Run Locally (91, :349-439), Environment Variables (74, :275-348), Meeting Calls (72, :124-195), Endpoints (57, :478-534) and Configuration Validation (51, :47-97). About 330 lines (README.md:37-243 and :535-592) describe individual features.

## Accuracy checks

| Check | Method | Result |
|---|---|---|
| Environment table | every row grepped in `src/`; diffed with `.env.example` | 64/64 exist; identical set to `.env.example` |
| Defaults | read `src/core/config.py:12-153`, `custom_sip_reach/config.py:29`, `inbound_bridge.py:56` | match |
| Endpoints | `@router.*` in `src/api/routes/*.py` + prefixes in `src/api/server.py:161-178` | 50 routes, all listed |
| Paths and links | each backticked `src/`/`docs/`/`scripts/` path and each relative link tested with `-e` | all exist |
| Dispatcher polling (README.md:117-120) | `src/services/outbound_dispatcher/dispatcher.py:804-828` | stale: event-driven via Change Streams, 30 s safety poll; the 2 s sleep at :484 is the bridge-alive wait, not queue polling |
| "All three are read-only" (README.md:91) | table above it | four scripts listed |
| `mkdocs` commands (README.md:455,461) | `pyproject.toml:15-16` | mkdocs is a project dependency; needs `uv run` (AGENTS.md:80 uses it) |
| Local dependencies | `docker-compose.yml` services | only `api`, `sip_dispatcher`, `agent`; no MongoDB or LiveKit server, and the README never says how to start them |
| Licence / contributing | `ls` | no `LICENSE`, no `CONTRIBUTING.md` |

## Overlap with docs/

| README section | Already covered in |
|---|---|
| Provider API Keys (:37-45) | `docs/api/assistant/{get,list,update}.md` |
| Configuration Validation + Diagnostics (:47-96) | `docs/reference/troubleshooting.md`, `docs/reference/compatibility.md` |
| Exotel Outbound Lifecycle, Outbound Queueing (:98-122) | `docs/api/calls/flow.md`, `docs/api/calls/queue-status.md`, `docs/architecture/call-flows.md` |
| Meeting Calls (:124-194) | `docs/api/calls/meeting-call.md`, `docs/architecture/meeting-calls.md`, `docs/guides/meeting-connector.md` |
| Passthrough (:196-231) | `docs/api/calls/passthrough.md` |
| Hold Detection (:233-242) | `docs/architecture/audio-pipeline.md`, `docs/architecture/call-flows.md` |
| Response Envelope (:253-263) | `docs/api/errors.md` |
| Assistant Modes (:535-563) | `docs/architecture/runtime-modes.md`, `docs/reference/compatibility.md` |
| Audio Library (:565-584) | `docs/api/audio/*.md` |
| Max Call Duration (:586-592) | `docs/api/assistant/create.md`, `docs/api/calls/webhook.md` |
| Project Structure (:594-724) | `AGENTS.md` `## Project structure` |
| "What This Project Does" (:5-29) | `docs/features.md` (343 lines) |

## README standard

The pack's own standard (`core-be-structure-service/references/readme-standard.md`) requires envelope, endpoints table, structure tree, data stores and stack sections. Part of the README's length was added to satisfy it. The standard does not require feature deep-dives, design rationale or a file-level tree, so the proposed outline keeps each required section in a compact form.
