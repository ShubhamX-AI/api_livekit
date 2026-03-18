# Inbound Calls

## Overview

Inbound routing maps normalized dialed numbers to assistants and dispatches the mapped assistant into a new LiveKit room.

!!! info "Provider support status"

    Inbound calling currently supports **Exotel only**.
    **Twilio inbound is not implemented yet**.
    Outbound provider behavior differs; see [Outbound Calls](../calls/index.md).

## Current Behavior

- `/inbound` routes currently support `exotel` as the active provider.
- Request schema may include `twilio`, but non-Exotel assign requests return `400`.
- Number normalization is enforced before persistence and lookup.
- Detached mappings remain stored but do not route inbound calls.
- Deleting a mapping deactivates it and releases the number for reuse.

## Endpoints and Guides

- [Manage Numbers](manage.md)
- [Inbound Call Flow](flow.md)
