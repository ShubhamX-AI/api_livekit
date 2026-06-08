# Upload Audio

Upload an audio clip into the library. Any common audio format is accepted; the server transcodes it to WAV 48 kHz mono and enforces the 30-second limit.

- **URL**: `/audio/upload`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `multipart/form-data`

### Form Fields

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | file | Yes | Audio file in any common format (mp3, m4a, ogg, wav, …). Must be **30 seconds or shorter**. |
| `audio_name` | string | Yes | Human-readable name for the clip. |
| `transcript` | string | Yes | The literal spoken words. Added to the model's chat context at call time so it knows it already greeted. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Whether the upload succeeded. |
| `message` | string | Human-readable message. |
| `data.audio_id` | string | Unique identifier for the stored asset (UUID). |
| `data.duration_seconds` | number | Measured duration of the clip. |
| `data.url` | string | Temporary presigned URL to download/preview the stored WAV. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success — audio stored. |
| 400 | Bad Request — file is not decodable audio, has no audio stream, is too large, or is longer than 30 seconds. |
| 401 | Unauthorized — invalid or missing Bearer token. |
| 500 | Server Error. |

### Example

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/audio/upload" \
     -H "Authorization: Bearer <your_api_key>" \
     -F "file=@greeting.mp3" \
     -F "audio_name=Friendly welcome" \
     -F "transcript=Hi, thanks for calling Acme. How can I help you today?"
```

**Response:**

```json
{
  "success": true,
  "message": "Audio uploaded successfully",
  "data": {
    "audio_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "duration_seconds": 4.2,
    "url": "https://<bucket>.s3.<region>.amazonaws.com/greeting_audio/f47ac10b-...wav?..."
  }
}
```

Attach the returned `audio_id` to an assistant via [Update Assistant](../assistant/update.md):

```json
{ "assistant_greeting_audio": { "enabled": true, "audio_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479" } }
```
