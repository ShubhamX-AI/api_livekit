# Generate Web Call Token

Create a LiveKit room and return a participant token for browser or mobile web calls.

- **URL**: `/web_call/getToken`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Assistant ID to run in the generated room. |
| `metadata` | object | No | Optional key-value data injected into assistant placeholders. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates whether token creation succeeded. |
| `message` | string | Human-readable status message. |
| `data` | object | Generated room and access token payload. |
| `data.room_name` | string | Unique LiveKit room created for this web call. |
| `data.token` | string | Participant access token for joining the room. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - Token generated successfully. |
| 400 | Bad Request - Invalid input or token generation failure. |
| 401 | Unauthorized - Invalid or missing Bearer token. |
| 404 | Not Found - Assistant not found for the authenticated user. |
| 500 | Server Error - Internal error while generating the token. |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/getToken" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "metadata": {
             "name": "John Doe",
             "plan": "premium"
           }
         }'
```

### Example Response

```json
{
  "success": true,
  "message": "Token generated successfully",
  "data": {
    "room_name": "550e8400-e29b-41d4-a716-446655440000_ab12cd34",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```
