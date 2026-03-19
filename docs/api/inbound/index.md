# Inbound Calls

## Overview

Inbound routing maps a dialed number to a stored inbound mapping and dispatches the mapped assistant into a LiveKit room.

Each active inbound mapping now has two independent attachments:

- `assistant_id` (required for successful routing)
- `inbound_context_strategy_id` (optional caller-context lookup)

## What Is Required vs Optional

Required for a successful inbound call:

- A matching active inbound mapping for the normalized dialed number.
- A valid active assistant attached to that mapping.

Optional:

- A valid inbound context strategy attached to the mapping.

## What Happens If Optional Parts Are Missing

If no strategy is attached:

- Call routing still succeeds.
- The assistant still starts.
- Prompt rendering uses call metadata only, without fetched `context` values.

If strategy lookup fails at runtime:

- Call still continues.
- The worker falls back to default prompt behavior.
- Failure details are recorded in activity logs as `inbound_context_lookup`.

## Provider Support

!!! info "Provider support status"

    Inbound calling currently supports **Exotel only**.
    **Twilio inbound is not implemented yet**.
    Outbound provider behavior differs; see [Outbound Calls](../calls/index.md).

## Current API Behavior

- `/inbound` routes currently support `service="exotel"` for assignment.
- Number normalization is enforced before persistence and runtime lookup.
- Detached mappings remain stored but do not route calls until an assistant is reattached.
- Deleting a mapping deactivates it and releases the number for reuse.

## Related Guides

- [Manage Numbers](manage.md)
- [Inbound Call Flow](flow.md)
- [Inbound Context Strategies](../inbound-context-strategy/index.md)
