# Update Assistant

Update the configuration of an existing assistant.

- **URL**: `/assistant/update/{assistant_id}`
- **Method**: `PATCH`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter      | Type   | Description                          |
| :------------- | :----- | :----------------------------------- |
| `assistant_id` | string | The UUID of the assistant to update. |

### Request Body

Only provide the fields you want to update. All fields are optional.

!!! note "Important"

    If updating `assistant_tts_model` and `assistant_tts_config`, both should be updated together to ensure consistency.

| Field                         | Type   | Description                                       |
| :---------------------------- | :----- | :------------------------------------------------ |
| `assistant_name`              | string | The new name of the assistant (1-100 characters). |
| `assistant_description`       | string | The new description.                              |
| `assistant_prompt`            | string | The new system prompt.                            |
| `assistant_tts_model`         | string | The new TTS provider (`cartesia` or `sarvam`).    |
| `assistant_tts_config`        | object | The new TTS configuration object.                 |
| `assistant_start_instruction` | string | The new start instruction.                        |
| `assistant_speaks_first`     | boolean | Whether the assistant should speak first.         |
| `assistant_end_call_url`      | string | The new webhook URL.                              |

### Response Schema

| Field               | Type    | Description                                |
| :------------------ | :------ | :----------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful. |
| `message`           | string  | Human-readable success message.            |
| `data`              | object  | Contains the updated assistant ID.         |
| `data.assistant_id` | string  | The ID of the updated assistant.           |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Assistant updated successfully.       |
| 400  | Bad Request - Invalid input data.               |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 404  | Not Found - Assistant does not exist.           |
| 500  | Server Error - Internal server error.           |

### Example: Update TTS Configuration

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_name": "Updated Support Bot",
           "assistant_tts_model": "sarvam",
           "assistant_tts_config": {
             "speaker": "meera",
             "target_language_code": "hi-IN"
           },
           "assistant_speaks_first": false
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant updated successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```
