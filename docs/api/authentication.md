# Authentication

This section covers the authentication endpoints for the LiveKit Agents API.

## Overview

All API endpoints (except creating an API key) require authentication via the `x-api-key` header. API keys are scoped to individual users and provide access to all resources created by that user.

## Create API Key

Generate a new API key for a user. This endpoint does **not** require authentication and is typically used for initial setup.

- **URL**: `/auth/create-key`
- **Method**: `POST`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `user_name` | string | Yes | The name of the user (1-100 characters). |
| `user_email` | string | Yes | The email address of the user. |
| `org_name` | string | No | The name of the organization (max 100 characters). |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates if the operation was successful. |
| `message` | string | Human-readable success message. |
| `data` | object | Contains the API key details. |
| `data.api_key` | string | The generated API key. **Store this securely - it cannot be retrieved later.** |
| `data.user_name` | string | The user's name. |
| `data.org_name` | string | The organization name (if provided). |
| `data.user_email` | string | The user's email address. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - API key created successfully. |
| 400 | Bad Request - Invalid input data (missing required fields, invalid email). |
| 500 | Server Error - Internal server error during key creation. |

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

### Example Response (200 OK)

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

### Example Error Response (400 Bad Request)

```json
{
  "success": false,
  "message": "Invalid email address",
  "data": null
}
```

---

## Check API Key

Verify if an API key is valid and retrieve the associated user details.

- **URL**: `/auth/check-key`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Request Headers

| Header | Required | Description |
| :--- | :--- | :--- |
| `x-api-key` | Yes | The API key to verify. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates if the operation was successful. |
| `message` | string | Human-readable status message. |
| `data` | object | Contains user details if key is valid. |
| `data.user_name` | string | The user's name. |
| `data.org_name` | string | The organization name (if set). |
| `data.user_email` | string | The user's email address. |
| `data.created_at` | string | ISO 8601 timestamp of when the key was created. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - API key is valid. |
| 401 | Unauthorized - Invalid or missing API key. |
| 500 | Server Error - Internal server error during validation. |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/auth/check-key" \
     -H "x-api-key: lvk_a1b2c3d4e5f6..."
```

### Example Response (200 OK)

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

### Example Error Response (401 Unauthorized)

```json
{
  "success": false,
  "message": "Invalid API key",
  "data": null
}
```

---

## Security Best Practices

!!! warning "Important"

    - **Store API keys securely** - never commit them to version control
    - **Rotate keys regularly** - create new keys and deprecate old ones
    - **Use environment variables** - never hardcode keys in your application
    - **Monitor usage** - check the `created_at` timestamp to track key age

### Example: Using Environment Variables

```python
import os
import requests

# Load API key from environment
API_KEY = os.getenv("LIVEKIT_API_KEY")
if not API_KEY:
    raise ValueError("LIVEKIT_API_KEY environment variable not set")

# Use in requests
headers = {"x-api-key": API_KEY}
response = requests.get("https://api-livekit-vyom.indusnettechnologies.com/assistant/list", headers=headers)
```

---

## Next Steps

Once you have your API key, you can:

1. [Create an Assistant](assistant.md) - Configure your AI agent
2. [Set up Tools](tools.md) - Add custom capabilities
3. [Configure SIP Trunks](sip.md) - Enable telephony
4. [Make Outbound Calls](calls.md) - Start voice conversations
