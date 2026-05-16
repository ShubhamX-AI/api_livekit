# Inbound Call

Inbound calls (Exotel only) route incoming calls to an assistant based on the dialed number.

Prerequisite: complete [Step 1–3](index.md) to have an `assistant_id`.

## C1 — Assign an Inbound Number

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound/assign" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ASSISTANT_ID",
    "service": "exotel",
    "inbound_config": {
      "phone_number": "+918044319240"
    }
  }'
```

When someone dials `+918044319240`, the assistant is automatically dispatched into a LiveKit room.

See [Inbound Calls](../api/inbound/index.md) and [Inbound Context Strategies](../api/inbound-context-strategy/index.md) for full details.
