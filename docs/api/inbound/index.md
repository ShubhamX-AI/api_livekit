# Inbound Calls

This section covers inbound number management and the Exotel inbound SIP bridge.

## Overview

Inbound calls are routed by looking up the dialed phone number in the `inbound_sip` collection and dispatching the mapped assistant into a new LiveKit room.

## Current Behavior

- Only `exotel` is supported by the `/inbound` API routes today.
- The request schema still includes `twilio`, but `POST /inbound/assign` returns `400` for non-Exotel services.
- Phone numbers are normalized before storage and lookup, so uniqueness is enforced on the normalized value.
- A mapping can exist without an assistant after detach, but detached mappings do not receive inbound calls.
- Deleting a mapping marks it inactive and releases the normalized number for reuse.

## Endpoints

- [Manage Numbers](manage.md)
- [Inbound Call Flow](flow.md)
