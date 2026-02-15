# Authentication

This section covers the authentication endpoints for the LiveKit Agents API.

## Create API Key

Generate a new API key for a user.

- **URL**: `/auth/create-key`
- **Method**: `POST`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `user_name` | string | Yes | The name of the user. |
| `org_name` | string | No | The name of the organization. |
| `user_email` | string | Yes | The email address of the user. |

### Response

Returns the generated API key. **Store this key securely as it cannot be retrieved later.**

### Example

```bash
curl -X POST "http://localhost:8000/auth/create-key" \
     -H "Content-Type: application/json" \
     -d '{
           "user_name": "John Doe",
           "org_name": "Acme Corp",
           "user_email": "john@example.com"
         }'
```

```json
{
  "success": true,
  "message": "API key created successfully, Store it securely",
  "data": {
    "api_key": "lvk_...",
    "user_name": "John Doe",
    "org_name": "Acme Corp",
    "user_email": "john@example.com"
  }
}
```

## Check API Key

Verify if an API key is valid and retrieve the associated user details.

- **URL**: `/auth/check-key`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Request Headers

| Header | Required | Description |
| :--- | :--- | :--- |
| `x-api-key` | Yes | The API key to verify. |

### Response

Returns the user and organization details associated with the API key.

### Example

```bash
curl -X GET "http://localhost:8000/auth/check-key" \
     -H "x-api-key: lvk_..."
```

```json
{
  "success": true,
  "message": "API key is valid",
  "data": {
    "user_name": "John Doe",
    "org_name": "Acme Corp",
    "user_email": "john@example.com",
    "created_at": "2023-10-27T10:00:00.000000"
  }
}
```
