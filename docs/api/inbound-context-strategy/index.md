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

## Current Strategy Types

Only one strategy type is supported:

- `webhook`: sends a POST request to your endpoint and expects a JSON response with a top-level `context` object.

## Runtime Behavior

The lookup is optional and non-blocking.

- If lookup succeeds, the returned `context` object is available to prompt templates.
- If lookup fails (timeout, HTTP error, invalid JSON, invalid shape), the call continues with default prompt behavior.
- Failures are visible in activity logs as `inbound_context_lookup`.

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

Lookup is non-blocking by design.

- Timeout, HTTP error, invalid JSON, invalid payload shape, missing URL, or inactive strategy does not fail the call.
- The assistant still starts.
- Prompt rendering continues without `context.*`.
- The lookup outcome is written to activity logs as `inbound_context_lookup`.

!!! note "Contract stability"

    This payload reflects current runtime behavior.
    New keys may be added in a backward-compatible way.
    Existing keys are expected to remain stable.

## Security and Response Masking

When strategies are returned from list/details endpoints:

- Sensitive header values (for keys like `authorization`, `token`, `secret`, `api-key`) are masked as `****`.

## Endpoints

- [Create Strategy](create.md)
- [Update Strategy](update.md)
- [List Strategies](list.md)
- [Get Strategy Details](details.md)
- [Delete Strategy](delete.md)
