# Attach Tools to Assistant

Enable a set of tools for a specific assistant.

- **URL**: `/tool/attach/{assistant_id}`
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
| `tool_ids` | array | Yes      | List of tool IDs to attach (at least one required). |

### Response Schema

| Field               | Type    | Description                                |
| :------------------ | :------ | :----------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful. |
| `message`           | string  | Human-readable success message with count. |
| `data`              | object  | Contains attachment details.               |
| `data.assistant_id` | string  | The assistant ID.                          |
| `data.tool_ids`     | array   | Updated list of all attached tool IDs.     |

### HTTP Status Codes

| Code | Description                                         |
| :--- | :-------------------------------------------------- |
| 200  | Success - Tools attached successfully.              |
| 400  | Bad Request - Invalid input (empty tool_ids array). |
| 401  | Unauthorized - Invalid or missing Bearer token.     |
| 404  | Not Found - Assistant or one/more tools not found.  |
| 500  | Server Error - Internal server error.               |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/attach/550e8400-e29b-41d4-a716-446655440000" \
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
  "message": "Attached 1 tool(s) to assistant",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
  }
}
```
