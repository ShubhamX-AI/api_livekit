# Calls by Service

## Overview

Returns call count and duration metrics grouped by telephony service (exotel, twilio, or web).

## Endpoint

- **URL**: `/analytics/calls/by-service`
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
| `data.services` | array | List of per-service metrics. |
| `data.services[].service` | string | Service name: `exotel`, `twilio`, `web`, or `unknown`. |
| `data.services[].total_calls` | integer | Total calls via this service. |
| `data.services[].total_duration_minutes` | float | Total duration in minutes. |
| `data.services[].total_duration_hours` | float | Total duration in hours. |
| `data.services[].completed_calls` | integer | Count of completed calls. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/analytics/calls/by-service" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Example Response

```json
{
  "success": true,
  "message": "Calls by service fetched successfully",
  "data": {
    "services": [
      {
        "service": "exotel",
        "total_calls": 180,
        "total_duration_minutes": 810.00,
        "total_duration_hours": 13.50,
        "completed_calls": 165
      },
      {
        "service": "twilio",
        "total_calls": 120,
        "total_duration_minutes": 540.00,
        "total_duration_hours": 9.00,
        "completed_calls": 110
      },
      {
        "service": "web",
        "total_calls": 42,
        "total_duration_minutes": 170.75,
        "total_duration_hours": 2.85,
        "completed_calls": 40
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- Calls created before service tracking was added may appear as `unknown`.
