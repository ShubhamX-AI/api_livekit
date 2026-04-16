# Queue Status

Inspect the status of an outbound call request after it has been queued.

- **URL**: `/call/queue/{queue_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

## Path Parameter

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `queue_id` | string | Yes | The queue id returned by `POST /call/outbound`. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates if the operation was successful. |
| `message` | string | Human-readable success message. |
| `data.queue_id` | string | The outbound queue item id. |
| `data.status` | string | Queue state: `pending`, `dispatching`, `dispatched`, or `failed`. |
| `data.to_number` | string | Destination number in E.164 format. |
| `data.call_service` | string | Telephony provider: `twilio` or `exotel`. |
| `data.queued_at` | string | ISO-8601 timestamp when the item was queued. |
| `data.dispatched_at` | string or `null` | ISO-8601 timestamp when dispatch succeeded. |
| `data.retry_count` | integer | Number of dispatch retries attempted so far. |
| `data.last_error` | string or `null` | Most recent dispatch error, if any. |

## Queue State Meanings

| Status | Meaning |
| :--- | :--- |
| `pending` | Waiting for the dispatcher to pick it up. |
| `dispatching` | Dispatcher reserved a slot and is creating the LiveKit room/provider call. |
| `dispatched` | The call was handed off successfully to the provider flow. Final call outcome will continue in call logs/webhooks. |
| `failed` | Dispatch failed permanently after retry exhaustion. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Queue item found and returned. |
| 401 | Unauthorized - invalid or missing Bearer token. |
| 404 | Queue item not found for the authenticated user. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/call/queue/QUEUE_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Queue status retrieved",
  "data": {
    "queue_id": "8b7df5ea0fdc497ea4f44bd31954a387",
    "status": "dispatching",
    "to_number": "+15550100000",
    "call_service": "twilio",
    "queued_at": "2026-04-16T08:20:15.152308+00:00",
    "dispatched_at": null,
    "retry_count": 0,
    "last_error": null
  }
}
```

!!! note
    `dispatched` means the queue handoff succeeded. To track the live call outcome (`answered`, `completed`, `busy`, `no_answer`, and so on), use the end-call webhook or assistant call logs.
