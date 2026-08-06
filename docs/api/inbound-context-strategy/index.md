# Inbound Context Strategies

## Overview

Inbound context strategies let you fetch caller-specific data before the assistant prompt is rendered for an inbound call.

This resource is independent from assistants:

- You create and manage strategies in `/inbound_context_strategy`.
- You optionally attach a strategy to an inbound number mapping in `/inbound`.
- The lookup runs only for inbound calls that have an attached strategy.

## Why This Exists

Inbound calls often need per-caller personalization, such as CRM profile, ticket status, account plan, or language preference.

Without a strategy:

- Inbound calls still route normally.
- The assistant still starts normally.
- Prompt rendering uses call metadata only, not fetched CRM context.

With a strategy:

- The worker can fetch extra context and expose it to prompt templates as `{{context.*}}`.

## How a Strategy Gets Triggered

**A strategy attaches to an inbound phone number, not to an assistant.** The link lives on the inbound number mapping (`InboundSIP.inbound_context_strategy_id`), set through `POST /inbound/assign` or `PATCH /inbound/update/{inbound_id}` — see [Manage Inbound Numbers](../inbound/manage.md).

That means the same assistant can be reached on three different numbers with three different strategies, or with none at all. The assistant document has no strategy field.

The chain on a live call:

```
Caller dials your inbound number
  │
  ├─ SIP INVITE arrives at the inbound listener
  ├─ The bridge looks up the InboundSIP mapping by normalized number
  ├─ inbound_context_strategy_id is copied into the agent dispatch metadata
  │
  ├─ The agent worker starts and resolves the strategy (must be active,
  │  and owned by the same account as the assistant)
  ├─ The worker POSTs to your webhook and reads the `context` object
  ├─ {{context.*}} placeholders render into the prompt
  │
  └─ The session starts and the assistant greets the caller
```

The webhook fires from the **agent worker**, not from the SIP listener, and it happens once per call just before the prompt is rendered.

### Without a Strategy the Call Is Unaffected

An inbound number with no strategy attached works exactly as it always has. There is nothing to configure and nothing to turn on.

| Situation | What happens to the call |
| :--- | :--- |
| No `inbound_context_strategy_id` on the mapping | Connects normally. The lookup is skipped entirely — no webhook, no added latency. |
| Strategy id set, but the strategy was deleted or deactivated | Connects normally. Logged as `inbound_context_lookup`. |
| Strategy active, but the webhook times out, errors, or returns bad JSON | Connects normally. Logged as `inbound_context_lookup`. |

In every one of those cases the assistant still starts and still greets. The only difference is that `{{context.*}}` placeholders render as empty strings.

What *does* stop an inbound call is unrelated to strategies:

- No active mapping for the dialed number, or no assistant on it → SIP `480 Temporarily Unavailable`
- The assistant is inactive → SIP `480 Temporarily Unavailable`
- Concurrency cap reached → SIP `486 Busy Here`

## Current Strategy Types

Only one strategy type is supported:

- `webhook`: sends a POST request to your endpoint and expects a JSON response with a top-level `context` object.

## Runtime Behavior

The lookup is optional, and it never fails the call — but it **does block session start**.

- The context has to be in the prompt before the assistant speaks, so the worker waits for your webhook before starting the session. The caller hears silence for that window.
- Keep `timeout_seconds` low. Default is `2.0`, allowed range is `0.5`–`10.0`. A 10-second timeout means up to 10 seconds of dead air on a failing lookup.
- If lookup succeeds, the returned `context` object is available to prompt templates.
- If lookup fails (timeout, HTTP error, invalid JSON, invalid shape), the call continues with default prompt behavior.
- Failures are visible in activity logs as `inbound_context_lookup`.

Request mechanics:

- **No retries.** One attempt per call.
- **Redirects are followed.** The whole chain must finish inside `timeout_seconds`.
- The timeout is a total budget covering connect, write, and read — not a per-read timeout.

## Webhook Request Payload

When a strategy is attached to an inbound mapping and a call is routed, the worker sends a `POST` request to your configured strategy URL.

```json
{
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_name": "Support Bot",
  "room_name": "550e8400_abc123",
  "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
  "strategy_name": "CRM lookup",
  "strategy_type": "webhook",
  "call_type": "inbound",
  "service": "exotel",
  "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
  "caller_number": "+919876543210",
  "inbound_number": "918044319240"
}
```

### Request Field Reference

| Field | Type | Always Present | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Assistant ID selected from inbound mapping. |
| `assistant_name` | string | Yes | Assistant name from the selected assistant. |
| `room_name` | string | Yes | LiveKit room name for the current call. |
| `strategy_id` | string | Yes | Strategy ID being executed. |
| `strategy_name` | string | Yes | Strategy display name. |
| `strategy_type` | string | Yes | Strategy type. Currently always `webhook`. |
| `call_type` | string | Yes | Always `inbound` for this flow. |
| `service` | string | Yes | Inbound provider. Currently `exotel`. |
| `inbound_id` | string | Yes | Inbound mapping identifier. |
| `caller_number` | string | Usually | Caller number parsed by bridge. |
| `inbound_number` | string | Usually | Normalized dialed inbound number. |

Headers sent to your webhook:

- `Content-Type: application/json`
- Any custom headers configured in `strategy_config.headers`

## Expected Webhook Response

Your webhook must return JSON with a top-level `context` object.

```json
{
  "context": {
    "customer_name": "John Doe",
    "ticket_id": "TCK-1234",
    "plan": "Enterprise"
  }
}
```

If valid, these values are available in templates as `{{context.customer_name}}`, `{{context.ticket_id}}`, and so on.

### Quick Test with curl

You can test your endpoint with a representative inbound payload:

```bash
curl -X POST "https://your-webhook-url" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <optional-token>" \
  -d '{
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Bot",
    "room_name": "550e8400_abc123",
    "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
    "strategy_name": "CRM lookup",
    "strategy_type": "webhook",
    "call_type": "inbound",
    "service": "exotel",
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "caller_number": "+919876543210",
    "inbound_number": "918044319240"
  }'
```

## Failure and Fallback Contract

Lookup is best-effort by design: no failure mode drops the call.

- Timeout, HTTP error, invalid JSON, invalid payload shape, missing URL, or inactive strategy does not fail the call.
- The assistant still starts.
- Prompt rendering continues without `context.*`.
- The lookup outcome is written to activity logs as `inbound_context_lookup`.

!!! note "Contract stability"

    This payload reflects current runtime behavior.
    New keys may be added in a backward-compatible way.
    Existing keys are expected to remain stable.

## URL Requirements

`strategy_config.url` is validated when you create or update a strategy. A URL that fails any of these is rejected with `400`.

| Rule | Accepted | Rejected |
| :--- | :--- | :--- |
| Scheme must be `http` or `https` | `https://crm.example.com/ctx`<br>`http://crm.example.com/ctx` | `ftp://crm.example.com/ctx` |
| Host must not be a private, loopback, link-local, or reserved IP | `https://203.0.113.10/ctx` | `https://127.0.0.1/ctx`<br>`https://10.0.0.5/ctx`<br>`https://192.168.1.10/ctx`<br>`https://169.254.169.254/…` |
| Host must not be an internal name | `https://internal.example.com/ctx` | `https://localhost/ctx`<br>`https://metadata.google.internal/ctx` |

Rejection looks like this:

```json
{
  "detail": [
    {
      "loc": ["body", "strategy_config", "url"],
      "msg": "Value error, url host '169.254.169.254' resolves to a non-public address"
    }
  ]
}
```

!!! warning "Prefer https"

    Plain `http` is accepted so existing integrations keep working, but the request carries the caller's phone number and any `Authorization` header you configured — in cleartext. Use `https` unless you have a specific reason not to.

The check runs on the URL you send, at write time. DNS is not re-resolved when the call actually fires.

## Security and Response Masking

When strategies are returned from list/details endpoints:

- Sensitive header values (for keys like `authorization`, `token`, `secret`, `api-key`) are masked as `****`.
- Sending a masked `****` value back on create/update is rejected with `400`. Send the real value, or omit `strategy_config` to leave the stored one untouched — otherwise a GET-edit-PATCH round trip would silently overwrite your real token with the mask.

## Updating Headers

`strategy_config.headers` is **merged key by key**, so you can change one header without resending the rest. Send a header with a `null` value to delete just that header.

Starting from stored headers `{"Authorization": "Bearer old", "X-Tenant-Id": "acme"}`:

| PATCH `headers` | Resulting stored headers |
| :--- | :--- |
| `{"X-Region": "in"}` | `Authorization: Bearer old`, `X-Tenant-Id: acme`, `X-Region: in` |
| `{"Authorization": "Bearer new"}` | `Authorization: Bearer new`, `X-Tenant-Id: acme` |
| `{"X-Tenant-Id": null}` | `Authorization: Bearer old` |
| omitted entirely | unchanged |

Other `strategy_config` keys (`url`, `timeout_seconds`) replace outright — sending `timeout_seconds` alone leaves `url` and `headers` untouched.

Two rules apply to every update:

- `strategy_type` and `strategy_config` must be sent together, or neither.
- `strategy_name`, `strategy_type`, and `strategy_config` may not be `null`. Omit a field to leave it unchanged.

See [Update Strategy](update.md) for runnable examples.

## Endpoints

- [Create Strategy](create.md)
- [Update Strategy](update.md)
- [List Strategies](list.md)
- [Get Strategy Details](details.md)
- [Delete Strategy](delete.md)
