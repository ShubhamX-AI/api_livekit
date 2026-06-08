# List Audio

Return the caller's active audio assets, paginated.

- **URL**: `/audio/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Query Parameters

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `page` | integer | No | Page number (default: 1). |
| `limit` | integer | No | Items per page, 1–100 (default: 10). |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `data.audios` | array | List of audio assets (newest first). |
| `data.pagination` | object | `total`, `page`, `limit`, `total_pages`. |

Each audio object includes `audio_id`, `audio_name`, `transcript`, `s3_key`, `duration_seconds`, `filename`, `created_by_email`, `created_at`, `is_active`.

### Example

```bash
curl "https://api-livekit-vyom.indusnettechnologies.com/audio/list?page=1&limit=10" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Audio assets retrieved successfully",
  "data": {
    "audios": [
      {
        "audio_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "audio_name": "Friendly welcome",
        "transcript": "Hi, thanks for calling Acme. How can I help you today?",
        "duration_seconds": 4.2,
        "filename": "greeting.mp3",
        "is_active": true
      }
    ],
    "pagination": { "total": 1, "page": 1, "limit": 10, "total_pages": 1 }
  }
}
```
