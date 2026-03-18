# Health Check

## Overview

Use this endpoint to verify the API service is up and responding.

## Endpoint

- **URL**: `/health`
- **Method**: `GET`
- **Authentication**: Not required

## Request

No parameters or request body.

## Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | `true` when the service is healthy. |
| `message` | string | Service health message. |
| `data` | object | Additional payload (currently empty object). |

## HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Service is healthy and operational. |
| 500 | Unexpected server error. |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/health"
```

## Example Response

```json
{
  "success": true,
  "message": "Service is healthy and operational",
  "data": {}
}
```
