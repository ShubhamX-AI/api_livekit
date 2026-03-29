# Analytics Dashboard

## Overview

Returns an at-a-glance summary of call activity for the authenticated user, including total calls, duration, status breakdown, and period-based counts (today, this week, this month).

## Endpoint

- **URL**: `/analytics/dashboard`
- **Method**: `GET`
- **Authentication**: Required

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
| `data.total_calls` | integer | Total number of calls in range. |
| `data.total_duration_minutes` | float | Total call duration in minutes. |
| `data.total_duration_hours` | float | Total call duration in hours. |
| `data.avg_duration_minutes` | float | Average call duration in minutes. |
| `data.calls_by_status` | object | Counts keyed by call status. |
| `data.calls_today` | integer | Calls placed today. |
| `data.calls_this_week` | integer | Calls placed this week. |
| `data.calls_this_month` | integer | Calls placed this month. |
| `data.date_range.start_date` | string | Applied start date. |
| `data.date_range.end_date` | string | Applied end date. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Dashboard data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/analytics/dashboard?start_date=2026-03-01T00:00:00Z&end_date=2026-03-28T23:59:59Z" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Dashboard analytics fetched successfully",
  "data": {
    "total_calls": 342,
    "total_duration_minutes": 1520.75,
    "total_duration_hours": 25.35,
    "avg_duration_minutes": 4.45,
    "calls_by_status": {
      "completed": 310,
      "failed": 12,
      "initiated": 5,
      "answered": 15
    },
    "calls_today": 8,
    "calls_this_week": 45,
    "calls_this_month": 342,
    "date_range": {
      "start_date": "2026-03-01T00:00:00Z",
      "end_date": "2026-03-28T23:59:59Z"
    }
  }
}
```

## Notes

- All duration values are rounded to two decimal places.
- Period counts (today, this week, this month) are computed relative to UTC.
- Status breakdown includes all statuses present in the data; missing statuses default to `0`.
