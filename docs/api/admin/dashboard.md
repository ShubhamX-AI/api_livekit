# Admin Dashboard

## Overview

Returns a cross-tenant summary of call activity across all users, including total calls, duration, status breakdown, and the number of active users.

## Endpoint

- **URL**: `/admin/analytics/dashboard`
- **Method**: `GET`
- **Authentication**: Super-admin required

## Request

### Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `start_date` | datetime | No | 30 days ago | ISO 8601 start of range. |
| `end_date` | datetime | No | Now | ISO 8601 end of range. |
| `user_email` | string | No | -- | Narrow results to a specific user. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.total_calls` | integer | Total calls across all users. |
| `data.total_duration_minutes` | float | Total call duration in minutes. |
| `data.total_duration_hours` | float | Total call duration in hours. |
| `data.avg_duration_minutes` | float | Average call duration in minutes. |
| `data.total_active_users` | integer | Distinct users who made calls in the range. |
| `data.calls_by_status` | object | Counts keyed by call status. |
| `data.date_range.start_date` | string | Applied start date. |
| `data.date_range.end_date` | string | Applied end date. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Dashboard data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 403 | Forbidden (API key is not a super-admin). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/admin/analytics/dashboard" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Admin dashboard fetched successfully",
  "data": {
    "total_calls": 2450,
    "total_duration_minutes": 11025.50,
    "total_duration_hours": 183.76,
    "avg_duration_minutes": 4.50,
    "total_active_users": 18,
    "calls_by_status": {
      "completed": 2200,
      "failed": 250
    },
    "date_range": {
      "start_date": "2026-02-26T00:00:00Z",
      "end_date": "2026-03-28T23:59:59Z"
    }
  }
}
```

## Notes

- `calls_by_status` returns two keys: `completed` and `failed` (where `failed` includes busy, no_answer, rejected, timeout, and unreachable).
- `total_active_users` counts distinct `created_by_email` values with at least one call in the range.
- When `user_email` is provided, the response is equivalent to a single-user dashboard.
