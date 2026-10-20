# Decision records

One file per significant decision: the problem, what was decided, and what follows from it. Read
the relevant record before reversing a decision. If you do reverse one, write a new record and
set the old one's status to `Superseded by 000N`.

| # | Decision | Date | In one line |
|---|---|---|---|
| [0001](0001-ask-openai-before-storing-a-config.md) | Ask OpenAI whether it will run a config before storing it | 2026-08 | Closes the silent call: retired ids removed, two cached fail-open OpenAI gates, speech ids allowlisted, keyless providers refused. |
| [0002](0002-optional-tts-and-cascade-llm-knobs.md) | Add TTS and cascade LLM knobs as optional keys | 2026-08 | Every new knob is optional and absent means the old behaviour; ElevenLabs gets `NOT_GIVEN`, never `None`. |
| [0003](0003-never-echo-secrets-in-errors.md) | Never echo a secret in an error response | 2026-08 | `redact_text` / `redact_validation_errors` on every error path; provider keys capped at 500 characters. |
| [0004](0004-one-rule-table-for-every-mode.md) | Reject impossible mode combinations with one rule table | 2026-08 | `validate_mode_config` is the only rule table, re-run on stored row + PATCH; Gemini only in realtime; `extra="forbid"` everywhere. |
| [0005](0005-adopt-gemini-3.8-live.md) | Move to livekit-agents 1.8.2 and make Gemini 3.8 Live the default | 2026-09 | New default `gemini-3.8-live`, mid-session guard removed, Vertex-only model refused, Deepgram limited to priced models. |
| [0006](0006-duplex-mode-gpt-6-and-new-speech-models.md) | Add duplex mode, GPT-6 and new speech models (1.6.0) | 2026-10 | GPT-Live duplex mode, GPT-6, new ElevenLabs/Sarvam models, `gpt-5.1`/`gpt-5.4-nano` removed, ignored TTS settings are a 422. |

## Template for a new record

Name the file `000N-<short-slug>.md`, using the next free number. Phrase the title as the
decision, for example "Validate every assistant config before storing it".

```markdown
# 000N. <Title as a decision>

- **Status:** Accepted
- **Date:** YYYY-MM

## Context

The problem, in plain words. What was going wrong, or what new need appeared.

## Decision

What was decided. Keep every rule, model id, number and file path.

## Consequences

What follows from it. What must not be reintroduced. Which migration scripts to run, and when.

## Where in the code

| What | File | Symbol |
|---|---|---|
```
