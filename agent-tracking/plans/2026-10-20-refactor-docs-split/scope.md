# Scope — 2026-10-20-refactor-docs-split

- **Type:** refactor (documentation)
- **Requested by:** Shubham Halder (backend engineer)
- **Date:** 2026-10-20
- **Follows:** `2026-10-20-audit-readme` (findings R-01 to R-14)

## Original request (verbatim)

The task came out of a conversation. The user's words, in order:

> Okay, so the main thing for the README is for the developers, so that they could understand and an overall understanding, and they could run the code and how to run the code and those kind of things. Then there comes the doc part. The docs is for the MK docs is hosted. It is for the general public. They can take a look into all the APIs, their payloads, and all of the structure works, and they can understand my system and they can use my hosted system. And also there's an MCP that is attached with that MK doc, so that they can attach that MCP with their agent and they can understand and they can write code on that. And then another part comes the architecture, how this is built and how this works and everything. Those part is also for the developers. Okay, and now the thing is, I'm a little bit confused, like how to write those things and everything. So how should this be done, as because the architectures and everything is also hosted and those kind of things. So give me ideas and how this can be built and how this can be properly production greatly done, so that developers can also have a look, normal users can also have a look and everything. Give me ideas and help me understand.

> Okay, but there should be kind of a link between dev docs and the docs, public docs kind of a thing. I don't know whether there should be any link or not, or how this can be done. And if someone wants to understand the dev docs, so, and also the dev docs should be properly structured and properly done, and the public docs also, the MK docs should also be properly structured, properly done. I think now what is present, it's all is already very much structured and properly done, and all things are updated, I guess. And your idea looks good. That should be done. But what if someone wants to understand the system, how it works, and what happens there?

> A

## Decisions already made

- Option (a): internal architecture leaves the public site. `docs/` = public (MkDocs site + MCP); new `dev-docs/` = developers only, plain Markdown in the repo, not in `mkdocs.yml`, not indexed by the MCP.
- Links go one way: `dev-docs/` and `README.md` may link to public docs; public docs never link to `dev-docs/`.
- Public docs gain a "How It Works" section (`docs/concepts/`) at C4 levels 1-2 (context + containers), with no file paths. `dev-docs/` covers levels 3-4 (components + code).
- README becomes the developer front door (~200 lines, working quickstart), per the audit outline.

## Agreed scope

| Question | Answer |
|----------|--------|
| Target (paths) | `README.md`, `docs/architecture/`, `docs/reference/` (code references), new `docs/concepts/`, new `dev-docs/`, `mkdocs.yml` nav plus `AGENTS.md` (ADR extraction) and `pyproject.toml`/`uv.lock` (`mkdocs-redirects`) |
| Depth | Full: production quality, plain language a newcomer can follow (user: "production graded… high quality… simpler way so that everyone can understand") |
| Out of scope | Source code; `docs/api/` and `docs/getting-started/` content (already public-clean) except the stale "three modes" line |
| Constraints | No information lost: every fact deleted from one place exists in its new home first. `uv run mkdocs build --strict` and `scripts/check_mermaid.py` stay green |
| Success criteria | No `src/` reference left in `docs/`; README ~200 lines with a quickstart that works on a clean machine; every old public URL either still works or redirects |
| Report format (HTML / MD) | HTML |
| Severity cut-off | n/a |
| Type-specific answers | Facts may move between files; product behaviour does not change. Use the installed skills and plugins (user request) |

## Clarification log

| Question asked | User's answer |
|----------------|---------------|
| Internal architecture public (b) or moved to dev-docs (a)? | "A" |
| Q1 Delivery: one task, or phased (README first, review, then the rest)? | (a) phased: README first, user reviews, then the split |
| Q2 Old public URLs (`/architecture/...`): add `mkdocs-redirects` (new dependency), leave stub pages pointing to How It Works, or just remove? | (b) add `mkdocs-redirects` (new docs dependency, version verified before adding) |
| Q3 ADRs: turn the six "Recent changes" sections of `AGENTS.md` into `dev-docs/decisions/` and shrink `AGENTS.md` to rules + links? | (a) six "Recent changes" sections become `dev-docs/decisions/` ADRs; `AGENTS.md` shrinks to rules + links |
| Q4 Quickstart local deps: document manual commands only, or also add a `dev` compose profile with MongoDB (replica set) + `livekit-server --dev`? | (b) manual commands only; no compose change |
| Q5 `dev-docs/how-to/` recipes (add a model / provider / endpoint): write now or later? | (a) write the how-to recipes now |
| General instruction | "Everythign should be some production graded way.. and hily quality way.. snd soimpler way so that everyone can understadn . use the skills na pluglins" |
