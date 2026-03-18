# Activity Logs

## Overview

Use this endpoint to audit outbound actions performed during calls, including webhook tool calls and end-call webhook delivery.

## Endpoint

- **URL**: `/logs`
- **Method**: `GET`
- **Authentication**: Required

## Request

### Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `log_type` | string | No | — | Filter by `tool_call` or `end_call_webhook`. |
| `assistant_id` | string | No | — | Filter by assistant ID. |
| `room_name` | string | No | — | Filter by room name. |
| `page` | integer | No | `1` | Page number. |
| `limit` | integer | No | `50` | Page size (max `100`). |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.logs` | array | Activity log list. |
| `data.logs[].log_type` | string | `tool_call` or `end_call_webhook`. |
| `data.logs[].status` | string | `success` or `error`. |
| `data.logs[].assistant_id` | string | Assistant identifier. |
| `data.logs[].room_name` | string | LiveKit room name for the call. |
| `data.logs[].timestamp` | string | UTC timestamp. |
| `data.logs[].message` | string | Human-readable log summary. |
| `data.logs[].request_data` | object | Outbound payload details. |
| `data.logs[].response_data` | object | Received response payload. |
| `data.logs[].latency_ms` | integer | Request round-trip latency in milliseconds. |
| `data.total` | integer | Total matching records. |
| `data.page` | integer | Current page number. |
| `data.limit` | integer | Current page size. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Logs returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/logs?page=1&limit=20" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

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
        "message": "Tool called successfully",
        "request_data": {
          "url": "https://api.example.com/weather"
        },
        "response_data": {
          "temperature": 34
        },
        "latency_ms": 312
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 20
  }
}
```

## Notes

- Results are always scoped to the authenticated user.
- Logs are returned in descending timestamp order.
