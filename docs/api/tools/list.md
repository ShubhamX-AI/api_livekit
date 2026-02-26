# List Tools

List all active tools created by the current user.

- **URL**: `/tool/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Response Schema

| Field                        | Type    | Description                                |
| :--------------------------- | :------ | :----------------------------------------- |
| `success`                    | boolean | Indicates if the operation was successful. |
| `message`                    | string  | Human-readable success message.            |
| `data`                       | array   | List of tool objects.                      |
| `data[].tool_id`             | string  | Unique identifier for the tool.            |
| `data[].tool_name`           | string  | The name of the tool.                      |
| `data[].tool_description`    | string  | The description of the tool.               |
| `data[].tool_execution_type` | string  | Either `webhook` or `static_return`.       |
| `data[].tool_created_at`     | string  | ISO 8601 timestamp of creation.            |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Tools retrieved successfully.         |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/tool/list" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tools retrieved successfully",
  "data": [
    {
      "tool_id": "880e8400-e29b-41d4-a716-446655449999",
      "tool_name": "lookup_weather",
      "tool_description": "Get current weather information for a given location",
      "tool_execution_type": "webhook",
      "tool_created_at": "2024-01-15T10:00:00.000000"
    },
    {
      "tool_id": "990e8400-e29b-41d4-a716-446655449888",
      "tool_name": "get_support_email",
      "tool_description": "Get the customer support email address",
      "tool_execution_type": "static_return",
      "tool_created_at": "2024-01-15T11:00:00.000000"
    }
  ]
}
```
