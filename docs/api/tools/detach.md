# Detach Tools from Assistant

Remove a set of tools from a specific assistant.

- **URL**: `/tool/detach/{assistant_id}`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter      | Type   | Description                |
| :------------- | :----- | :------------------------- |
| `assistant_id` | string | The UUID of the assistant. |

### Request Body

| Field      | Type  | Required | Description                                         |
| :--------- | :---- | :------- | :-------------------------------------------------- |
| `tool_ids` | array | Yes      | List of tool IDs to detach (at least one required). |

### Response Schema

| Field               | Type    | Description                                  |
| :------------------ | :------ | :------------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful.   |
| `message`           | string  | Human-readable success message.              |
| `data`              | object  | Contains detachment details.                 |
| `data.assistant_id` | string  | The assistant ID.                            |
| `data.tool_ids`     | array   | Updated list of remaining attached tool IDs. |

### HTTP Status Codes

| Code | Description                                         |
| :--- | :-------------------------------------------------- |
| 200  | Success - Tools detached successfully.              |
| 400  | Bad Request - Invalid input (empty tool_ids array). |
| 401  | Unauthorized - Invalid or missing Bearer token.     |
| 404  | Not Found - Assistant not found.                    |
| 500  | Server Error - Internal server error.               |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/detach/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Detached tool(s) from assistant",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "tool_ids": []
  }
}
```
