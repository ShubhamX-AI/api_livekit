# Calls by Phone Number

## Overview

Returns call count and duration metrics grouped by destination phone number. Optionally filter by a specific assistant.

## Endpoint

- **URL**: `/analytics/calls/by-phone-number`
- **Method**: `GET`
- **Authentication**: Required

## Request

### Query Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `start_date` | datetime | No | 30 days ago | ISO 8601 start of range. |
| `end_date` | datetime | No | Now | ISO 8601 end of range. |
| `assistant_id` | string | No | -- | Filter by a specific assistant. |

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.phone_numbers` | array | List of per-number metrics. |
| `data.phone_numbers[].phone_number` | string | Destination phone number. |
| `data.phone_numbers[].total_calls` | integer | Total calls to this number. |
| `data.phone_numbers[].total_duration_minutes` | float | Total duration in minutes. |
| `data.phone_numbers[].total_duration_hours` | float | Total duration in hours. |
| `data.phone_numbers[].avg_duration_minutes` | float | Average call duration in minutes. |
| `data.phone_numbers[].completed_calls` | integer | Count of completed calls. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/analytics/calls/by-phone-number?assistant_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Calls by phone number fetched successfully",
  "data": {
    "phone_numbers": [
      {
        "phone_number": "+919876543210",
        "total_calls": 15,
        "total_duration_minutes": 67.50,
        "total_duration_hours": 1.13,
        "avg_duration_minutes": 4.50,
        "completed_calls": 14
      },
      {
        "phone_number": "+918765432109",
        "total_calls": 8,
        "total_duration_minutes": 32.20,
        "total_duration_hours": 0.54,
        "avg_duration_minutes": 4.03,
        "completed_calls": 7
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- The `phone_number` value is the `to_number` from the call record.
