# Outbound Calls

## Overview

Outbound calls initiate a LiveKit room, dispatch an assistant, and place a call through the selected SIP service.

!!! info "Provider support status"

    Outbound supports **Twilio** (managed SIP) and **Exotel** (custom bridge).
    Inbound routing is **Exotel only** right now.
    **Twilio inbound is not implemented yet**; see [Inbound Calls](../inbound/index.md).

## Endpoints and Guides

- [Trigger Outbound Call](trigger.md)
- [Generate Web Call Token](web-call.md)
- [Call Flow](flow.md)
- [End Call Webhook](webhook.md)
- [Call Status Tracking](tracking.md)
- [Best Practices](best-practices.md)

The exact post-call webhook payload contract is documented in [End Call Webhook](webhook.md).

For inbound number routing, see [Inbound Calls](../inbound/index.md).
