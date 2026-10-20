# Research — 2026-10-20-refactor-docs-split

Baseline taken 2026-10-20 on `master` (clean tree, HEAD `3ef3a1e`).

## Baseline checks

| Check | Command | Result |
|---|---|---|
| Docs build | `uv run mkdocs build --strict` | passes; two INFO notes about `#110` / `#100` anchors in `changelog.md` (pre-existing, not errors) |
| Diagrams | `uv run python scripts/check_mermaid.py` | 21 diagrams, 0 broken |
| README size | `wc -l README.md` | 762 lines |
| Architecture size | `wc -l docs/architecture/*.md` | 2,169 lines in 9 pages |
| Code paths in public docs | `grep -rc 'src/' docs/` | architecture 19 refs; reference 29 (compatibility 11, models 9, usage-accounting 5, troubleshooting 3, pricing 1); guides/meeting-connector 5; changelog 3; features 1 |

## Behaviour surface that must not change

- Every public URL under the MkDocs site. Pages that move get a redirect (`mkdocs-redirects`), so old links keep working.
- The MCP server (`src/api/mcp_docs.py:21`) indexes `docs/**/*.md`. After the split it must still index every public page, and must not index `dev-docs/`. No code change is needed: `dev-docs/` sits outside `DOCS_DIR`.
- `tests/test_provider_pricing.py:136` reads `docs/reference/pricing.md` — that page stays where it is.
- Validation messages in `src/` point users to `docs/reference/troubleshooting.md` (`capabilities.py:21`, `assistant_guard.py:270`), `docs/reference/models.md` (`tts_config.py:43,69,120,129`) and `docs/api/calls/webhook.md` (`assistant.py:75`). None of those pages move.
- One code comment points at a page that moves: `src/core/agents/audio_denoise.py:27` → `docs/architecture/audio-pipeline.md`. It is a comment, so updating it changes no behaviour.
- `scripts/check_mermaid.py:52` scans `docs/` and `README.md`; it must also scan `dev-docs/` or diagrams there go unchecked.

## What each architecture page holds (public vs internal)

| Page (lines) | Public part — goes to `docs/concepts/` | Internal part — goes to `dev-docs/` |
|---|---|---|
| `index.md` (38) | becomes the new "How it works" overview (C4 levels 1-2) | "where configuration is decided" → `dev-docs/architecture.md` |
| `runtime-modes.md` (263) | assistant modes, latency and cost (:56-157) | API startup services, server topology (:5-55), Sarvam parallel tap, native transcription (:158-263) |
| `cascade-pipeline.md` (451) | why it exists, configuration, turn detection behaviour, text-only, feature compatibility | per-stage build details (STT/LLM/TTS factories), usage metering internals |
| `duplex-mode.md` (121) | almost all (comparison, what happens, limits, cost) | "Deploying" (:116-121) |
| `call-flows.md` (500) | web, managed SIP, queue states, passthrough, provider matrix | Exotel custom SIP reach (:64-198), dispatcher internals and capacity control (:199-415) |
| `meeting-calls.md` (352) | what a meeting call is, lifecycle, failure paths seen by the user | dispatch topology, audio flow, ownership, capacity, deployment boundary |
| `audio-pipeline.md` (269) | hold/resume behaviour (one paragraph) | RTP processing, input speech gate, noise-reduction branching, utterance guard |
| `inbound.md` (75) | inbound call sequence as the user sees it | components and failure paths inside the bridge |
| `dependencies.md` (100) | — | all → `dev-docs/operations/deployment.md` |

## Inbound links to `architecture/` (must be updated)

`docs/index.md:53`, `docs/changelog.md:49,122,221`, `docs/features.md:11`, `docs/guides/index.md:5`,
`docs/guides/meeting-connector.md:12`, `docs/getting-started/end-to-end-example.md:103`,
`docs/reference/compatibility.md:446,447`, `docs/reference/models.md:9,58,113,570`
(two of them use anchors: `#llm-context-truncation`, `#turn-detection`).

## mkdocs-redirects

Checked on PyPI 2026-10-20:

| Version | Released | Requires | Source |
|---|---|---|---|
| 1.2.2 | 2024-11-07 | `mkdocs>=1.1.1` | github.com/mkdocs/mkdocs-redirects |
| 1.2.3 (latest) | 2026-03-28 | `mkdocs<=1.6.1,>=1.2`, **`properdocs>=1.6.5`** | github.com/ProperDocs/properdocs-redirects |

1.2.3 moved to a different GitHub organisation and pulls in `properdocs`, a separate documentation
engine (a fork of MkDocs), as a new transitive dependency. 1.2.2 is the last release from the
official `mkdocs` organisation and needs nothing beyond MkDocs, which is installed at 1.6.1
(`uv.lock`). **Recommendation: pin `mkdocs-redirects==1.2.2`.** The package must also go into
`docker/requirements-control.txt`, because `docker/Dockerfile.control:27` builds the site.

## Stale content found

- `docs/getting-started/index.md:29-50` says "three execution modes" and omits `duplex`.
- README findings R-03, R-09 to R-13 from `2026-10-20-audit-readme`.

## AGENTS.md "Recent changes" sections (ADR candidates)

`AGENTS.md:311` (1.6.0 duplex/GPT-6), `:338` (silent call), `:369` (Gemini 3.8 Live), `:409`
(TTS + cascade knobs), `:450` (secret redaction + key caps), `:463` (mode guardrails). About 190
lines. Each records a decision and its reason, which is what an ADR is. The `AGENTS.md`
"Definition of done" and "where truth lives" table list `docs/architecture/cascade-pipeline.md`,
which moves, so both must be updated.
