# API Response and Errors

## Overview

All endpoints return a standard envelope with `success`, `message`, and `data`.

## Response Envelope

```json
{
  "success": true,
  "message": "Human-readable result",
  "data": {}
}
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | `true` for successful operations, `false` for failures. |
| `message` | string | Human-readable status description. |
| `data` | object \| array \| null | Endpoint payload; error responses may return `null` or `{}`. |

## HTTP Status Codes

### Success

| Code | Meaning | Notes |
| :--- | :--- | :--- |
| `200` | OK | Standard success response used by current routes. |

### Client Errors

| Code | Meaning | When Used |
| :--- | :--- | :--- |
| `400` | Bad Request | Invalid request body, unsupported values, or failed validation in route logic. |
| `401` | Unauthorized | Missing or invalid Bearer API key. |
| `404` | Not Found | Requested resource does not exist or is not visible in user scope. |
| `422` | Unprocessable Entity | FastAPI validation error for malformed input payloads. |

### Server and Upstream Errors

| Code | Meaning | When Used |
| :--- | :--- | :--- |
| `500` | Internal Server Error | Unhandled exception in API service logic. |
| `502` | Bad Gateway | Integration-level upstream/provider failure. Availability depends on endpoint implementation. |
| `504` | Gateway Timeout | Integration-level upstream timeout. Availability depends on endpoint implementation. |

## Notes

- Current routes generally return `200` on successful create/update/delete operations.
- Route-specific pages are the source of truth for endpoint-specific statuses.
- `502` and `504` are not guaranteed on every route. For example, asynchronous flows such as `POST /call/outbound` with Exotel can return `202 Accepted` first and later report final provider outcome via webhook `data.call_status`.
