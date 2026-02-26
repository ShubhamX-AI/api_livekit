# Update Tool

Update an existing tool's configuration.

- **URL**: `/tool/update/{tool_id}`
- **Method**: `PATCH`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter | Type   | Description                     |
| :-------- | :----- | :------------------------------ |
| `tool_id` | string | The UUID of the tool to update. |

### Request Body

Only provide the fields you want to update. All fields are optional.

| Field                   | Type   | Description                                        |
| :---------------------- | :----- | :------------------------------------------------- |
| `tool_name`             | string | The new name (must follow snake_case format).      |
| `tool_description`      | string | The new description.                               |
| `tool_parameters`       | array  | New parameter definitions (replaces all existing). |
| `tool_execution_type`   | string | New execution type (`webhook` or `static_return`). |
| `tool_execution_config` | object | New execution configuration.                       |

### Response Schema

| Field          | Type    | Description                                |
| :------------- | :------ | :----------------------------------------- |
| `success`      | boolean | Indicates if the operation was successful. |
| `message`      | string  | Human-readable success message.            |
| `data`         | object  | Contains the updated tool ID.              |
| `data.tool_id` | string  | The ID of the updated tool.                |

### HTTP Status Codes

| Code | Description                                             |
| :--- | :------------------------------------------------------ |
| 200  | Success - Tool updated successfully.                    |
| 400  | Bad Request - Invalid input data or no fields provided. |
| 401  | Unauthorized - Invalid or missing Bearer token.         |
| 404  | Not Found - Tool does not exist.                        |
| 500  | Server Error - Internal server error.                   |

### Example: Update Webhook URL

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/tool/update/880e8400-e29b-41d4-a716-446655449999" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_execution_config": {
             "url": "https://api.new-weather.com/v1/current",
             "timeout": 10,
             "headers": {
               "Authorization": "Bearer new_token"
             }
           }
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Tool updated successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999"
  }
}
```
