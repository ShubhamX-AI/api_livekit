# Authentication and API Keys

## Overview

All protected endpoints require `Authorization: Bearer <api_key>`. API keys are user-scoped.

## Create API Key

### Endpoint

- **URL**: `/auth/create-key`
- **Method**: `POST`
- **Authentication**: Not required

### Request

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `user_name` | string | Yes | Name of the user. |
| `user_email` | string | Yes | Email of the user. |
| `org_name` | string | No | Organization name. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.api_key` | string | Generated API key (store securely). |
| `data.user_name` | string | User name. |
| `data.org_name` | string | Organization name, if provided. |
| `data.user_email` | string | User email. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | API key created. |
| 400 | User already exists or request invalid. |
| 500 | Internal error during key creation. |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "John Doe",
    "org_name": "Acme Corp",
    "user_email": "john@example.com"
  }'
```

### Example Response

```json
{
  "success": true,
  "message": "API key created successfully, Store it securely",
  "data": {
    "api_key": "lvk_a1b2c3d4e5f6...",
    "user_name": "John Doe",
    "org_name": "Acme Corp",
    "user_email": "john@example.com"
  }
}
```

## Check API Key

### Endpoint

- **URL**: `/auth/check-key`
- **Method**: `GET`
- **Authentication**: Required

### Request

| Header | Required | Description |
| :--- | :--- | :--- |
| `Authorization` | Yes | `Bearer <your_api_key>` |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Operation status. |
| `message` | string | Result message. |
| `data.user_name` | string | User name. |
| `data.org_name` | string | Organization name, if present. |
| `data.user_email` | string | User email. |
| `data.created_at` | string | API key creation timestamp. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | API key is valid. |
| 401 | Invalid or missing Bearer token. |
| 500 | Internal validation error. |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/auth/check-key" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Example Response

```json
{
  "success": true,
  "message": "API key is valid",
  "data": {
    "user_name": "John Doe",
    "org_name": "Acme Corp",
    "user_email": "john@example.com",
    "created_at": "2024-01-15T10:00:00.000000"
  }
}
```

## Notes

- Keep API keys in environment variables or a secure secret manager.
- Treat API keys as credentials with full access to that user scope.
