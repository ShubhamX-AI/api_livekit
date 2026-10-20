# Developer documentation

These pages explain **how the platform is built**: the processes, the code that implements each
part, and why it is built that way. They are for people changing this repository.

They are not published. The public site (`docs/`, served at `/documentation` and over MCP at
`/mcp`) explains **what the platform does** for people calling the API. When a developer page
needs to describe behaviour a user sees, it links to the public page instead of repeating it.

## Reading order for someone new

1. [`README.md`](../README.md): run the system locally.
2. [How it works](../docs/concepts/index.md) (public): the parts of the system and the life of a call.
3. [Architecture](architecture.md): the same picture one level deeper, with the code behind each box.
4. The subsystem you are about to change (below).
5. [`AGENTS.md`](../AGENTS.md): the working rules for this repo, for people and coding agents.

## Subsystems

| Page | Covers |
|---|---|
| [Agent session](subsystems/agent-session.md) | Worker startup, how each assistant mode is built, voice features, transcription paths |
| [Speech and LLM stages](subsystems/speech-and-llm-stages.md) | STT, LLM and TTS factories; cascade stage details; turn detection; usage metering per stage |
| [Dispatcher and queue](subsystems/dispatcher-and-queue.md) | Outbound queue, dispatch loop, capacity caps, recovery |
| [Telephony (Exotel)](subsystems/telephony-exotel.md) | The custom SIP/RTP bridge, inbound routing, the audio pipeline, hold detection |
| [Meeting calls](subsystems/meeting-calls.md) | Google Meet dispatch topology, audio flow, readiness, ownership |
| [Validation and model support](subsystems/validation-and-models.md) | The four config gates, `model_support/`, the per-mode rule table |
| [Usage and pricing](subsystems/usage-and-pricing.md) | How usage is collected, folded and priced |

## How-to recipes

- [Add a model](how-to/add-a-model.md)
- [Add a provider](how-to/add-a-provider.md)
- [Add an endpoint](how-to/add-an-endpoint.md)

## Operations

- [Deployment](operations/deployment.md): images, hosts, the singleton dispatcher, capacity
- [Scripts](operations/scripts.md): diagnostics and one-off migrations

## Decisions

[`decisions/`](decisions/) holds one record per significant decision: the problem, what was decided,
and what follows from it. Read the relevant one before reversing a decision. New decisions get the
next number.

## How these pages are written

- **Plain English.** Write for a developer who joined this week. Short sentences, one idea per
  section, and define a term the first time it appears.
- **Picture first.** A page that describes a flow opens with a Mermaid diagram. Use `<br/>` for
  line breaks inside labels, never `\n`; `uv run python scripts/check_mermaid.py` checks every
  diagram here too.
- **Mechanism, not behaviour.** Say how and why the code does something. For what the user sees,
  link to the public page.
- **"Where in the code" at the end.** A table of file and function or class names. Name symbols,
  not line numbers: line numbers go stale with every edit.
- **History lives in decisions and the changelog.** A subsystem page describes the system as it
  is now. "We used to…" belongs in a decision record or `docs/changelog.md`.
- **Links are relative** and must resolve on GitHub. Public pages never link here.
