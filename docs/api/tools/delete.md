# Delete Tool

Soft-delete a tool. This will also remove the tool from any assistants that are currently using it.

- **URL**: `/tool/delete/{tool_id}`
- **Method**: `DELETE`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter | Type   | Description                     |
| :-------- | :----- | :------------------------------ |
| `tool_id` | string | The UUID of the tool to delete. |

### Response Schema

| Field          | Type    | Description                                |
| :------------- | :------ | :----------------------------------------- |
| `success`      | boolean | Indicates if the operation was successful. |
| `message`      | string  | Human-readable success message.            |
| `data`         | object  | Contains the deleted tool ID.              |
| `data.tool_id` | string  | The ID of the deleted tool.                |

### HTTP Status Codes

| Code | Description                                             |
| :--- | :------------------------------------------------------ |
| 200  | Success - Tool deleted successfully.                    |
| 401  | Unauthorized - Invalid or missing Bearer token.         |
| 404  | Not Found - Tool does not exist or is already inactive. |
| 500  | Server Error - Internal server error.                   |

### Example Request

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/tool/delete/880e8400-e29b-41d4-a716-446655449999" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tool deleted successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999"
  }
}
```
