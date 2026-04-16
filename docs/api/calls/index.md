# Outbound Calls

## Overview

Outbound calls are now queued first, then dispatched into LiveKit and the selected SIP service by a background dispatcher when capacity is available.

!!! info "Provider support status"

    Outbound supports **Twilio** (managed SIP) and **Exotel** (custom bridge).
    Inbound routing is **Exotel only** right now.
    **Twilio inbound is not implemented yet**; see [Inbound Calls](../inbound/index.md).

## Endpoints and Guides

- [Trigger Outbound Call](trigger.md)
- [Queue Status](queue-status.md)
- [Generate Web Call Token](web-call.md)
- [Call Flow](flow.md)
- [End Call Webhook](webhook.md)
- [Call Status Tracking](tracking.md)
- [Best Practices](best-practices.md)

The exact post-call webhook payload contract is documented in [End Call Webhook](webhook.md).

For inbound number routing, see [Inbound Calls](../inbound/index.md).
