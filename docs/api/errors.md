# API Errors

This section documents all HTTP status codes and error responses from the API.

## Response Structure

All API responses follow a consistent structure:

```json
{
  "success": boolean,
  "message": string,
  "data": object | array | null
}
```

- **`success`**: `true` for successful operations, `false` for errors
- **`message`**: Human-readable description of the result
- **`data`**: Contains response payload on success, `null` on error

## HTTP Status Codes

### 2xx Success Codes

| Code | Name | Description |
| :--- | :--- | :--- |
| `200` | OK | The request was successful. |
| `201` | Created | A new resource was created successfully (also returns `200`). |

### 4xx Client Errors

| Code | Name | Description |
| :--- | :--- | :--- |
| `400` | Bad Request | Invalid request format or missing required fields. |
| `401` | Unauthorized | Invalid or missing API key. |
| `404` | Not Found | Resource does not exist or is inactive. |
| `422` | Unprocessable Entity | Validation error in request data (handled as `400`). |

### 5xx Server Errors

| Code | Name | Description |
| :--- | :--- | :--- |
| `500` | Internal Server Error | Unexpected server error occurred. |
| `502` | Bad Gateway | Upstream service (LiveKit, MongoDB) unavailable. |
| `503` | Service Unavailable | Temporary overload or maintenance. |

---
