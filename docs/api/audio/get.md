# Get Audio Details

Return a single audio asset's metadata plus a temporary presigned download URL.

- **URL**: `/audio/{audio_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Field | Type | Description |
| :--- | :--- | :--- |
| `audio_id` | string | The audio asset ID. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `data` | object | The audio asset fields plus `url` (a temporary presigned download URL). |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success. |
| 401 | Unauthorized. |
| 404 | Not found — no active asset with that ID owned by the caller. |

### Example

```bash
curl "https://api-livekit-vyom.indusnettechnologies.com/audio/f47ac10b-58cc-4372-a567-0e02b2c3d479" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Audio asset retrieved successfully",
  "data": {
    "audio_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "audio_name": "Friendly welcome",
    "transcript": "Hi, thanks for calling Acme. How can I help you today?",
    "duration_seconds": 4.2,
    "url": "https://<bucket>.s3.<region>.amazonaws.com/greeting_audio/f47ac10b-...wav?..."
  }
}
```
