# Calls by Time

## Overview

Returns time-series call data bucketed by day, week, or month. Use this to visualize call volume and duration trends over time.

## Endpoint

- **URL**: `/analytics/calls/by-time`
- **Method**: `GET`
- **Authentication**: Required

## Request

### Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `start_date` | datetime | No | 30 days ago | ISO 8601 start of range. |
| `end_date` | datetime | No | Now | ISO 8601 end of range. |
| `granularity` | string | No | `day` | Time bucket size: `day`, `week`, or `month`. |
| `assistant_id` | string | No | -- | Filter by a specific assistant. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.time_series` | array | List of time-bucketed metrics. |
| `data.time_series[].date` | string | Bucket label (format depends on granularity). |
| `data.time_series[].total_calls` | integer | Total calls in this bucket. |
| `data.time_series[].total_duration_minutes` | float | Total duration in minutes. |
| `data.time_series[].total_duration_hours` | float | Total duration in hours. |
| `data.granularity` | string | The granularity that was applied. |

### Date Format by Granularity

| Granularity | Format | Example |
| :--- | :--- | :--- |
| `day` | `YYYY-MM-DD` | `2026-03-15` |
| `week` | `YYYY-Www` | `2026-W12` |
| `month` | `YYYY-MM` | `2026-03` |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/analytics/calls/by-time?granularity=week&start_date=2026-03-01T00:00:00Z" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Calls by time fetched successfully",
  "data": {
    "time_series": [
      {
        "date": "2026-W09",
        "total_calls": 42,
        "total_duration_minutes": 189.60,
        "total_duration_hours": 3.16
      },
      {
        "date": "2026-W10",
        "total_calls": 55,
        "total_duration_minutes": 247.50,
        "total_duration_hours": 4.13
      },
      {
        "date": "2026-W11",
        "total_calls": 63,
        "total_duration_minutes": 283.35,
        "total_duration_hours": 4.72
      }
    ],
    "granularity": "week"
  }
}
```

## Notes

- Results are sorted by date in ascending order.
- Buckets with zero calls are omitted from the response.
