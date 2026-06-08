# Delete Audio

Soft-delete an audio asset (sets `is_active=false`). Assistants still referencing it automatically fall back to the model-generated greeting on their next call.

- **URL**: `/audio/{audio_id}`
- **Method**: `DELETE`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Field | Type | Description |
| :--- | :--- | :--- |
| `audio_id` | string | The audio asset ID. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success — asset marked inactive. |
| 401 | Unauthorized. |
| 404 | Not found — no active asset with that ID owned by the caller. |

### Example

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/audio/f47ac10b-58cc-4372-a567-0e02b2c3d479" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Audio asset deleted successfully",
  "data": { "audio_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479" }
}
```

!!! note
    Soft-delete keeps the S3 object. Assistants pointing at a deleted asset are not auto-detached — they simply fall back to the model greeting until you attach a new asset or toggle the greeting off.
