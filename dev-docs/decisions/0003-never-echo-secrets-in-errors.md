# 0003. Never echo a secret in an error response, and cap provider keys at 500 characters

- **Status:** Accepted
- **Date:** 2026-08

## Context

Assistants carry provider API keys. Two paths could leak one back to a caller:

- An exception message (from a provider client, a database driver, a parser) can contain the key,
  and endpoints were interpolating raw exceptions into the HTTP `detail`.
- A Pydantic validation error includes the failing field's `input`, which for an `api_key` field
  *is* the secret.

Separately, the length cap on `api_key` fields differed by stage (100 characters on STT/TTS,
200 on LLM), which refused some real keys.

## Decision

- **Error responses never echo secrets.** `redact_text` in `src/core/providers/keys.py` scrubs
  secret-shaped substrings out of any exception message before it reaches an HTTP body:
  - labelled assignments such as `api_key=…` and `Authorization: Bearer …`;
  - key prefixes `sk-proj-`, `sk-ant-`, `AIza`, `ghp_`;
  - a bare `Bearer <jwt>`;
  - 32+-character opaque tokens.
- `redact_validation_errors` (same file) masks a failing field's `input` when the field `loc` is a
  secret name, and masks any nested dict value whose key is secret.
- **Endpoints must not interpolate a raw exception into `detail`.** Run it through `redact_text`
  first.
- **The provider key cap is 500 characters** on every `api_key` field (was 100 on STT/TTS, 200 on
  LLM). `ProviderApiKey` stays an `Annotated` type; the per-field `max_length=500` is intentional
  so a validation error names the offending field.

## Consequences

- Every new `HTTPException(detail=...)` built from an exception goes through `redact_text`.
  Reviewers should reject `detail=str(e)`.
- The app-wide handlers in `src/api/server.py` apply `redact_validation_errors` to every
  validation error and `redact_text` to every `HTTPException` detail. That is a safety net, not
  permission to skip redaction in the route: other exception paths do not pass through it. New
  request schemas are covered as long as secret fields use a secret name such as `api_key`.
- Do not move `max_length=500` into `ProviderApiKey` itself: the error would stop naming the
  field.

## Where in the code

| What | File | Symbol |
|---|---|---|
| Message scrubbing | `src/core/providers/keys.py` | `redact_text` |
| Validation error masking | `src/core/providers/keys.py` | `redact_validation_errors` |
| Key type | `src/core/providers/keys.py` | `ProviderApiKey` |
| Handlers that apply both | `src/api/server.py` | `validation_exception_handler`, `http_exception_handler` |
| Per-field cap | `src/api/models/api_schemas/config/{llm,stt,tts}_config.py` | each `api_key` field |
