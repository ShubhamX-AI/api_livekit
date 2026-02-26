# Delete Assistant

Soft-delete an assistant. Deleted assistants are not permanently removed but marked as inactive.

- **URL**: `/assistant/delete/{assistant_id}`
- **Method**: `DELETE`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter      | Type   | Description                          |
| :------------- | :----- | :----------------------------------- |
| `assistant_id` | string | The UUID of the assistant to delete. |

### Response Schema

| Field               | Type    | Description                                |
| :------------------ | :------ | :----------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful. |
| `message`           | string  | Human-readable success message.            |
| `data`              | object  | Contains the deleted assistant ID.         |
| `data.assistant_id` | string  | The ID of the deleted assistant.           |

### HTTP Status Codes

| Code | Description                                                  |
| :--- | :----------------------------------------------------------- |
| 200  | Success - Assistant deleted successfully.                    |
| 401  | Unauthorized - Invalid or missing Bearer token.              |
| 404  | Not Found - Assistant does not exist or is already inactive. |
| 500  | Server Error - Internal server error.                        |

### Example Request

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/assistant/delete/550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant deleted successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```
