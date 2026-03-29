# Admin Calls by Phone Number

## Overview

Returns cross-tenant call count and duration metrics grouped by destination phone number. Optionally filter by a specific user.

## Endpoint

- **URL**: `/admin/analytics/calls/by-phone-number`
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
| `data.phone_numbers` | array | List of per-number metrics. |
| `data.phone_numbers[].phone_number` | string | Destination phone number. |
| `data.phone_numbers[].total_calls` | integer | Total calls to this number. |
| `data.phone_numbers[].total_duration_minutes` | float | Total duration in minutes. |
| `data.phone_numbers[].total_duration_hours` | float | Total duration in hours. |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Data returned successfully. |
| 401 | Unauthorized (invalid or missing API key). |
| 403 | Forbidden (API key is not a super-admin). |
| 500 | Internal server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/admin/analytics/calls/by-phone-number?user_email=alice@example.com" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_API_KEY"
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
        "total_calls": 45,
        "total_duration_minutes": 202.50,
        "total_duration_hours": 3.38
      },
      {
        "phone_number": "+918765432109",
        "total_calls": 30,
        "total_duration_minutes": 135.00,
        "total_duration_hours": 2.25
      }
    ]
  }
}
```

## Notes

- Results are sorted by total duration in descending order.
- Without `user_email`, the response includes numbers called by all users.
