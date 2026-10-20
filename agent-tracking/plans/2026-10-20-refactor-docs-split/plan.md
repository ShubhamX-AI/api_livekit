# Plan — 2026-10-20-refactor-docs-split

**Goal:** give each audience one home. `README.md` gets developers running; `docs/` (site + MCP) serves API users and their agents; new `dev-docs/` explains how the system is built. Nothing is lost, no public URL breaks, and product behaviour is unchanged.

**Skills:** `core-be-workflow`, `core-be-refactor-code` (documentation refactor: Move, Split, Remove Duplication), `core-be-structure-service` (README standard), `mattpocock-skills:writing-for-agents` (for `AGENTS.md`), `livekit-docs` MCP (local LiveKit server command), `artifact-diagramming` guidance for diagrams, fresh-context `reviewer` subagent before the report.

**Writing rules for every page:** plain English a newcomer can follow; one idea per section; a diagram first where it helps; public pages name no source files; dev pages end with "Where in the code"; history goes to the changelog or an ADR, not into reference pages.

## Phase A — README (stop for user review after A4)

- [x] A1. Verify the local-dependency commands before writing them: MongoDB as a single-node replica set (Change Streams need one, `dispatcher.py:755`) and LiveKit `livekit-server --dev` (from `livekit-docs` MCP), plus the `MONGODB_URL` that works with them. Run them locally if Docker is available.
- [x] A2. For every README section being removed, confirm its facts exist in the target docs page (mapping in the audit research). Move any missing fact into that page first.
- [x] A3. Rewrite `README.md` to the 12-section outline (~200 lines): intro + modes table, architecture (one Mermaid diagram), requirements, numbered quickstart, environment table (unchanged), tests/lint/docs (`uv run mkdocs`), deploy, endpoints by router (14 rows), response envelope, top-level structure, data stores + stack, documentation links, licence. Fixes R-01 to R-13.
- [x] A4. Verify: `uv run mkdocs build --strict`; `uv run python scripts/check_mermaid.py`; every README link resolves; line count. **Stop: user reviews the README.**

## Phase B — split by audience

- [x] B1. Add `mkdocs-redirects==1.2.2` to `pyproject.toml` (via `uv add`) and `docker/requirements-control.txt`; register the plugin in `mkdocs.yml`. Verify the strict build.
- [x] B2. Create `dev-docs/` skeleton: `index.md` (reading order), `architecture.md`, `subsystems/`, `how-to/`, `operations/`, `decisions/`. Add `dev-docs` to `scripts/check_mermaid.py:52`.
- [x] B3. Write `docs/concepts/how-it-works.md` (C4 levels 1-2) and `dev-docs/architecture.md` (levels 2-3, links down to subsystems and up to the public page).
- [x] B4. Split each `docs/architecture/*.md` page per the research table, one page at a time: public part → `docs/concepts/` (assistant-modes, cascade, duplex, call-lifecycle, meeting-calls), internal part → `dev-docs/subsystems/` (agent-session, speech-stages, dispatcher-and-queue, telephony-exotel, meeting-calls) and `dev-docs/operations/deployment.md`. Delete the old page once both halves exist. Verify the strict build after each page.
- [x] B5. Add a redirect for each of the 9 old URLs; update the 14 inbound links (including the two anchors) and `mkdocs.yml` nav ("How It Works" replaces "Architecture"); update the comment at `src/core/agents/audio_denoise.py:27`.
- [x] B6. Remove `src/` paths from public docs (`reference/`, `guides/`, `changelog`, `features`): keep the user-facing fact, move the code pointer to the matching dev-docs page.
- [x] B7. Fix `docs/getting-started/index.md:29-50` ("three execution modes" → four, add duplex).
- [x] B8. Turn the six "Recent changes" sections of `AGENTS.md` into `dev-docs/decisions/0001-…` to `0006-…` (context, decision, consequences). Shrink `AGENTS.md` to rules + links; update its "Definition of done" docs list and "where truth lives" table for the new paths. Load `writing-for-agents` first.
- [x] B9. Write `dev-docs/how-to/add-a-model.md`, `add-a-provider.md`, `add-an-endpoint.md` from `AGENTS.md` and the code.
- [x] B10. `dev-docs/operations/`: deployment, diagnostics scripts, migrations.
- [x] B11. Verify everything (commands below), then a fresh-context reviewer subagent checks for lost facts, broken links and public pages that still leak internals.
- [x] B12. Report `agent-tracking/reports/2026-10-20-refactor-docs-split.html`; update INDEX.

## Files

Changed: `README.md`, `AGENTS.md`, `mkdocs.yml`, `pyproject.toml`, `uv.lock`, `docker/requirements-control.txt`, `scripts/check_mermaid.py` (one line), `src/core/agents/audio_denoise.py` (comment only), `docs/index.md`, `docs/features.md`, `docs/changelog.md`, `docs/getting-started/{index,end-to-end-example}.md`, `docs/guides/{index,meeting-connector}.md`, `docs/reference/*.md`.
Created: `docs/concepts/*.md` (~6), `dev-docs/**` (~20).
Deleted: `docs/architecture/*.md` (9, replaced by redirects).

## Risks

| Risk | Mitigation |
|---|---|
| A fact is lost in the move | Each old page is deleted only after both halves exist; reviewer subagent diffs old vs new content |
| Old URLs break for users and MCP clients | Redirect for every moved page; strict build checks internal links |
| New dependency pulls in more than expected | Pin 1.2.2 (no transitive deps beyond MkDocs); check `uv.lock` diff |
| Dev-docs links rot (no build checks them) | Verification greps every relative link in `dev-docs/` and tests that it exists |
| Agents follow stale paths in `AGENTS.md` | B8 updates every path there in the same step |

**Rollback:** nothing is committed by me. Every step is a working-tree change; `git restore` / `git clean` of the listed paths returns to `3ef3a1e`. Phase A alone can be kept while Phase B is reverted.

## Verification

```bash
uv run mkdocs build --strict                       # passes
uv run python scripts/check_mermaid.py             # 0 broken, now incl. dev-docs
grep -rn 'src/' docs/ | grep -v changelog          # no code paths in public docs (changelog history may keep them)
uv run python -m unittest discover -s tests        # green (pricing page test included)
uvx ruff check scripts/check_mermaid.py src/core/agents/audio_denoise.py
# relative links in dev-docs and README all resolve (scripted check run in progress.md)
```
