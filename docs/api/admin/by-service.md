# Admin Calls by Service

## Overview

Returns cross-tenant call count and duration metrics grouped by telephony service (exotel, twilio, or web).

## Endpoint

- **URL**: `/admin/analytics/calls/by-service`
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
| 403 | Forbidden (API key is not a super-admin). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/admin/analytics/calls/by-service" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_API_KEY"
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
        "total_calls": 1200,
        "total_duration_minutes": 5400.00,
        "total_duration_hours": 90.00,
        "completed_calls": 1100
      },
      {
        "service": "twilio",
        "total_calls": 800,
        "total_duration_minutes": 3600.00,
        "total_duration_hours": 60.00,
        "completed_calls": 740
      },
      {
        "service": "web",
        "total_calls": 450,
        "total_duration_minutes": 2025.50,
        "total_duration_hours": 33.76,
        "completed_calls": 430
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- Calls created before service tracking was added may appear as `unknown`.
