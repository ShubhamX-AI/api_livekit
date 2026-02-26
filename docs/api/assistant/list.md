# List Assistants

List assistants created by the current user with support for pagination, sorting, and date filtering.

- **URL**: `/assistant/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Query Parameters

| Parameter        | Type    | Required | Default                | Description                                                |
| :--------------- | :------ | :------- | :--------------------- | :--------------------------------------------------------- |
| `page`           | integer | No       | `1`                    | Page number for pagination (minimum: 1).                   |
| `limit`          | integer | No       | `10`                   | Number of items per page (minimum: 1, maximum: 100).       |
| `assistant_name` | string  | No       | -                      | Filter by assistant name (case-insensitive partial match). |
| `start_date`     | string  | No       | -                      | Start date for filtering (ISO 8601 format).                |
| `end_date`       | string  | No       | -                      | End date for filtering (ISO 8601 format).                  |
| `sort_by`        | string  | No       | `assistant_created_at` | Field to sort by.                                          |
| `sort_order`     | string  | No       | `desc`                 | Sort order: `asc` or `desc`.                               |

### Response Schema

| Field                                          | Type    | Description                                              |
| :--------------------------------------------- | :------ | :------------------------------------------------------- |
| `success`                                      | boolean | Indicates if the operation was successful.               |
| `message`                                      | string  | Human-readable success message.                          |
| `data`                                         | object  | Contains the list of assistants and pagination metadata. |
| `data.assistants`                              | array   | List of assistant objects.                               |
| `data.assistants[].assistant_id`               | string  | Unique identifier for the assistant.                     |
| `data.assistants[].assistant_name`             | string  | The name of the assistant.                               |
| `data.assistants[].assistant_tts_model`        | string  | The TTS provider used.                                   |
| `data.assistants[].assistant_tts_config`       | object  | Masked TTS configuration.                                |
| `data.assistants[].assistant_created_by_email` | string  | Email of the user who created the assistant.             |
| `data.pagination`                              | object  | Pagination metadata.                                     |
| `data.pagination.total`                        | integer | Total number of assistants matching the query.           |
| `data.pagination.page`                         | integer | Current page number.                                     |
| `data.pagination.limit`                        | integer | Number of items per page.                                |
| `data.pagination.total_pages`                  | integer | Total number of pages available.                         |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - List retrieved successfully.          |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/list?page=1&limit=10&sort_by=assistant_created_at&sort_order=desc" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Assistants retrieved successfully",
  "data": {
    "assistants": [
      {
        "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
        "assistant_name": "Support Bot",
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {
          "voice_id": "a16...275",
          "api_key": "Using System provided API Key"
        },
        "assistant_created_by_email": "admin@example.com"
      }
    ],
    "pagination": {
      "total": 1,
      "page": 1,
      "limit": 10,
      "total_pages": 1
    }
  }
}
```
