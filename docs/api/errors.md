# API Response and Errors

## Overview

All endpoints return a standard envelope with `success`, `message`, and `data`.

## Response Envelope

```json
{
  "success": true,
  "message": "Human-readable result",
  "data": {}
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | `true` for successful operations, `false` for failures. |
| `message` | string | Human-readable status description. |
| `data` | object \| array \| null | Endpoint payload; error responses may return `null` or `{}`. |

## HTTP Status Codes

### Success

| Code | Meaning | Notes |
| :--- | :--- | :--- |
| `200` | OK | Standard success response used by current routes. |

### Client Errors

| Code | Meaning | When Used |
| :--- | :--- | :--- |
| `400` | Bad Request | Invalid request body, unsupported values, or failed validation in route logic. Also: a configuration that is only unrunnable **once merged with what is already stored** — see below. |
| `401` | Unauthorized | Missing or invalid Bearer API key. |
| `404` | Not Found | Requested resource does not exist or is not visible in user scope. |
| `422` | Unprocessable Entity | Schema validation error, and any model/knob/voice/speaker combination this platform or the provider will not run. |

### `422` vs `400` on assistant configuration

Both mean "this configuration cannot run a call". The difference is *where the offending value
came from*:

| Code | Route | Meaning |
| :--- | :--- | :--- |
| `422` | `POST /assistant/create` | The request itself named the bad value. |
| `400` | `PATCH /assistant/update/{id}`, `POST /tool/attach/{id}`, `POST /tool/detach/{id}` | The request is well-formed on its own; it is the **combination with the stored row** that cannot run. A PATCH that changes only the model can be refused because of a knob already on the row, and attaching a tool can be refused because of a knob that was legal while the assistant had none. |

What gets rejected, and why each one matters — a config that reaches a call and is then refused
by the provider produces a call that connects and stays **silent**, on every turn, with no useful
log line:

| Rejected | Example detail |
| :--- | :--- |
| A model this platform does not support | `assistant_llm_config.model 'gpt-4o-realtime-preview' is not a realtime model — …` |
| A model the **account** no longer serves | `… cannot be used — the OpenAI account for this key does not serve it. Either the model has been retired by OpenAI or this account has no access to it.` |
| A knob the model cannot read | `assistant_llm_config.temperature is not supported by model 'gpt-5-mini' — reasoning models reject temperature — set reasoning_effort instead.` |
| A knob **value** the model refuses | `OpenAI rejected this configuration for model 'gpt-5-mini': Unsupported value: 'reasoning.effort' does not support 'none' with this model. (param: reasoning.effort)` |
| A `service_tier` the model cannot use | `assistant_llm_config.service_tier is not supported by model 'gpt-4.1-nano' — 'flex' is a gpt-5 generation tier …` |
| `tool_choice: "required"` with no tools attached | `… needs at least one tool — attach a tool (POST /assistant/attach-tools) or enable assistant_end_call_enabled, or use 'auto'` |
| An STT/TTS model id that does not exist | `'deepgram' does not have a STT model called 'nova-9' — choose one of: …` |
| A Sarvam speaker the pinned model cannot use | `'anushka' is a bulbul:v2 speaker and this platform runs bulbul:v3, whose roster shares no names with v2 — …` |
| A voice from the other vendor's roster | `assistant_llm_config.voice 'Puck' is a Gemini Live voice and cannot be used with provider 'openai' — …` |
| A provider with no API key anywhere | `assistant_stt_config.api_key is required for STT provider 'deepgram' — the server has no DEEPGRAM_API_KEY configured` |

Two of these checks call the provider. If the provider cannot be reached — network error, `401`,
`429`, `5xx` — the write is **allowed** rather than refused: a provider outage must not make
assistants un-editable, and the offline rules have already had their say.

Diagnosing one of these after the fact:
[Troubleshooting](../reference/troubleshooting.md).

### Server and Upstream Errors

| Code | Meaning | When Used |
| :--- | :--- | :--- |
| `500` | Internal Server Error | Unhandled exception in API service logic. |
| `502` | Bad Gateway | Integration-level upstream/provider failure. Availability depends on endpoint implementation. |
| `504` | Gateway Timeout | Integration-level upstream timeout. Availability depends on endpoint implementation. |

## Notes

- Current routes generally return `200` on successful create/update/delete operations.
- Route-specific pages are the source of truth for endpoint-specific statuses.
- `502` and `504` are not guaranteed on every route. For example, asynchronous flows such as `POST /call/outbound` with Exotel can return `202 Accepted` first and later report final provider outcome via webhook `data.call_status`.

## Secret redaction

Error responses never echo back secret material. Before any exception message or validation
detail reaches the response body, secret-shaped substrings are masked with `****`:

- **Validation errors (`422`)** — the `input` value of a field whose `loc` names a secret
  (`api_key`, `token`, `secret`, `password`, `authorization`) is replaced by `"****"`, as is
  any *nested* dict inside that value whose key is secret. Non-secret fields are unchanged.
- **Exception messages (`400`/`500`/`502`/`504`)** — free-form text is scrubbed for:
  - labelled assignments, e.g. `api_key=sk-...`, `Authorization: Bearer ...`;
  - key prefixes (`sk-proj-`, `sk-ant-`, `AIza`, `ghp_`, ...) and the full masked remainder;
  - `Bearer <token>` headers and any opaque 32+-character token that walks like a credential.

Opaque provider error details are logged server-side in full; only the HTTP body is scrubbed.
