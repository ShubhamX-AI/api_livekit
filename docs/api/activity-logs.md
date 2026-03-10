# Activity Logs

Activity logs record every outbound action the agent takes during a call — tool webhook calls and post-call webhook fires. Use this endpoint to audit what happened inside any call.

- **URL**: `/logs`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

Logs are scoped to the authenticated user. You cannot see logs belonging to other users.

---

## Query Parameters

| Parameter      | Type    | Required | Default | Description                                                  |
| :------------- | :------ | :------- | :------ | :----------------------------------------------------------- |
| `log_type`     | string  | No       | —       | Filter by type: `tool_call` or `end_call_webhook`.           |
| `assistant_id` | string  | No       | —       | Filter logs to a specific assistant.                         |
| `room_name`    | string  | No       | —       | Filter logs to a specific call room.                         |
| `page`         | integer | No       | `1`     | Page number for pagination.                                  |
| `limit`        | integer | No       | `50`    | Items per page (max: 100).                                   |

---

## Response Schema

| Field                       | Type    | Description                                              |
| :-------------------------- | :------ | :------------------------------------------------------- |
| `success`                   | boolean | Whether the request succeeded.                           |
| `message`                   | string  | Human-readable message.                                  |
| `data.logs`                 | array   | List of activity log objects.                            |
| `data.logs[].log_type`      | string  | `tool_call` or `end_call_webhook`.                       |
| `data.logs[].status`        | string  | `success` or `error`.                                    |
| `data.logs[].assistant_id`  | string  | Assistant involved in the call.                          |
| `data.logs[].room_name`     | string  | LiveKit room name (unique per call).                     |
| `data.logs[].timestamp`     | string  | ISO 8601 UTC timestamp of the event.                     |
| `data.logs[].message`       | string  | Human-readable one-liner describing the event.           |
| `data.logs[].request_data`  | object  | Outbound payload sent (URL + arguments).                 |
| `data.logs[].response_data` | object  | Response received (if successful).                       |
| `data.logs[].latency_ms`    | integer | Round-trip time in milliseconds.                         |
| `data.total`                | integer | Total logs matching the query.                           |
| `data.page`                 | integer | Current page.                                            |
| `data.limit`                | integer | Items per page.                                          |

---

## Log Types

### `tool_call`

Written every time an assistant calls a webhook tool during a live call. Captures the outbound URL, arguments sent, the response, and latency.

### `end_call_webhook`

Written after a call ends, when the system fires the assistant's configured `end_call_url`. Captures success or failure of that post-call notification.

---

## HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success — logs returned.                        |
| 401  | Unauthorized — invalid or missing Bearer token. |
| 500  | Server Error — internal server error.           |

---

## Example Requests

**Fetch all logs (paginated)**

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/logs?page=1&limit=20" \
     -H "Authorization: Bearer <your_api_key>"
```

**Filter to tool calls for a specific assistant**

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/logs?log_type=tool_call&assistant_id=550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer <your_api_key>"
```

**Filter to a single call room**

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/logs?room_name=550e8400_abc123" \
     -H "Authorization: Bearer <your_api_key>"
```

---

## Example Response

```json
{
  "success": true,
  "message": "Activity logs fetched successfully",
  "data": {
    "logs": [
      {
        "log_type": "tool_call",
        "status": "success",
        "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
        "room_name": "550e8400_abc123",
        "timestamp": "2026-03-10T09:15:42.000Z",
        "message": "Tool 'get_weather' called https://api.example.com/weather — 200",
        "request_data": {
          "url": "https://api.example.com/weather",
          "arguments": { "location": "Mumbai" }
        },
        "response_data": {
          "temperature": 34,
          "condition": "Sunny"
        },
        "latency_ms": 312
      },
      {
        "log_type": "end_call_webhook",
        "status": "success",
        "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
        "room_name": "550e8400_abc123",
        "timestamp": "2026-03-10T09:17:05.000Z",
        "message": "End-call webhook fired to https://crm.example.com/call-ended — 200",
        "request_data": {
          "url": "https://crm.example.com/call-ended",
          "arguments": {}
        },
        "response_data": { "received": true },
        "latency_ms": 145
      }
    ],
    "total": 2,
    "page": 1,
    "limit": 20
  }
}
```
