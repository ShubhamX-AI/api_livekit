# Outbound Calls

This section covers how to trigger outbound calls using your configured assistants and SIP trunks.

## Trigger Outbound Call

Initiate a call from an assistant to a phone number.

- **URL**: `/call/outbound`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | The ID of the assistant to use. |
| `trunk_id` | string | Yes | The ID of the SIP trunk to use. |
| `to_number` | string | Yes | The phone number to call (E.164 format). |
| `call_service` | string | Yes | `twilio` (currently the only supported service). |
| `metadata` | object | No | Optional metadata to pass to the call session. |

### Example

```bash
curl -X POST "http://localhost:8000/call/outbound" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "trunk_id": "ST_...",
           "to_number": "+15550200000",
           "call_service": "twilio",
           "metadata": {
             "campaign_id": "12345"
           }
         }'
```

```json
{
  "success": true,
  "message": "Outbound call triggered successfully",
  "data": {
    "room_name": "...",
    "agent_dispatch": {...},
    "participant": {...}
  }
}
```
