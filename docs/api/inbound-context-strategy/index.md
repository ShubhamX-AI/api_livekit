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

## Security and Response Masking

When strategies are returned from list/details endpoints:

- Sensitive header values (for keys like `authorization`, `token`, `secret`, `api-key`) are masked as `****`.

## Endpoints

- [Create Strategy](create.md)
- [Update Strategy](update.md)
- [List Strategies](list.md)
- [Get Strategy Details](details.md)
- [Delete Strategy](delete.md)
