# Get Tool Details

Fetch details for a specific tool.

- **URL**: `/tool/details/{tool_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter | Type   | Description           |
| :-------- | :----- | :-------------------- |
| `tool_id` | string | The UUID of the tool. |

### Response Schema

| Field                        | Type    | Description                                |
| :--------------------------- | :------ | :----------------------------------------- |
| `success`                    | boolean | Indicates if the operation was successful. |
| `message`                    | string  | Human-readable success message.            |
| `data`                       | object  | Complete tool configuration.               |
| `data.tool_id`               | string  | Unique identifier for the tool.            |
| `data.tool_name`             | string  | The name of the tool.                      |
| `data.tool_description`      | string  | The description of the tool.               |
| `data.tool_parameters`       | array   | List of parameter definitions.             |
| `data.tool_execution_type`   | string  | Either `webhook` or `static_return`.       |
| `data.tool_execution_config` | object  | Execution configuration.                   |
| `data.tool_created_at`       | string  | ISO 8601 timestamp of creation.            |
| `data.tool_updated_at`       | string  | ISO 8601 timestamp of last update.         |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Tool details retrieved.               |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 404  | Not Found - Tool does not exist or is inactive. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/tool/details/880e8400-e29b-41d4-a716-446655449999" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tool details retrieved successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999",
    "tool_name": "lookup_weather",
    "tool_description": "Get current weather information for a given location",
    "tool_parameters": [
      {
        "name": "location",
        "type": "string",
        "description": "City and state, e.g. San Francisco, CA",
        "required": true
      }
    ],
    "tool_execution_type": "webhook",
    "tool_execution_config": {
      "url": "https://api.weather.com/v1/current",
      "timeout": 5,
      "headers": {
        "Authorization": "Bearer weather_api_token"
      }
    },
    "tool_created_at": "2024-01-15T10:00:00.000000",
    "tool_updated_at": "2024-01-15T10:00:00.000000"
  }
}
```
