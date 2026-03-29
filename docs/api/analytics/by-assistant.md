# Calls by Assistant

## Overview

Returns call count and duration metrics grouped by assistant. Use this to compare workload across your assistants.

## Endpoint

- **URL**: `/analytics/calls/by-assistant`
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
| `data.assistants` | array | List of per-assistant metrics. |
| `data.assistants[].assistant_id` | string | Assistant identifier. |
| `data.assistants[].assistant_name` | string | Assistant display name. |
| `data.assistants[].total_calls` | integer | Total calls for this assistant. |
| `data.assistants[].total_duration_minutes` | float | Total duration in minutes. |
| `data.assistants[].total_duration_hours` | float | Total duration in hours. |
| `data.assistants[].avg_duration_minutes` | float | Average call duration in minutes. |
| `data.assistants[].completed_calls` | integer | Count of completed calls. |
| `data.assistants[].failed_calls` | integer | Count of failed calls. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/analytics/calls/by-assistant" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Calls by assistant fetched successfully",
  "data": {
    "assistants": [
      {
        "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
        "assistant_name": "Sales Bot",
        "total_calls": 210,
        "total_duration_minutes": 945.30,
        "total_duration_hours": 15.76,
        "avg_duration_minutes": 4.50,
        "completed_calls": 195,
        "failed_calls": 8
      },
      {
        "assistant_id": "661f9511-f3ac-52e5-b827-557766551111",
        "assistant_name": "Support Bot",
        "total_calls": 132,
        "total_duration_minutes": 575.45,
        "total_duration_hours": 9.59,
        "avg_duration_minutes": 4.36,
        "completed_calls": 120,
        "failed_calls": 4
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- Only assistants with at least one call in the date range are included.
