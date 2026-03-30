# Calls by User

## Overview

Returns call count and duration metrics grouped by user email. Use this to identify per-user resource consumption across the platform.

## Endpoint

- **URL**: `/admin/analytics/calls/by-user`
- **Method**: `GET`
- **Authentication**: Super-admin required

## Request

### Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `start_date` | datetime | No | 30 days ago | ISO 8601 start of range. |
| `end_date` | datetime | No | Now | ISO 8601 end of range. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.users` | array | List of per-user metrics. |
| `data.users[].user_email` | string | User email address. |
| `data.users[].total_calls` | integer | Total calls by this user. |
| `data.users[].total_duration_minutes` | float | Total duration in minutes. |
| `data.users[].total_duration_hours` | float | Total duration in hours. |
| `data.users[].avg_duration_minutes` | float | Average call duration in minutes. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 403 | Forbidden (API key is not a super-admin). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/admin/analytics/calls/by-user" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Calls by user fetched successfully",
  "data": {
    "users": [
      {
        "user_email": "alice@example.com",
        "total_calls": 450,
        "total_duration_minutes": 2025.00,
        "total_duration_hours": 33.75,
        "avg_duration_minutes": 4.50
      },
      {
        "user_email": "bob@example.com",
        "total_calls": 280,
        "total_duration_minutes": 1260.00,
        "total_duration_hours": 21.00,
        "avg_duration_minutes": 4.50
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- Only users with at least one call in the date range are included.
- `avg_duration_minutes` is calculated as `total_duration_minutes / total_calls` (derived from totals, not raw Mongo `$avg`), and returns `0` when `total_calls` is `0`. Duration values are rounded to two decimal places.
