# End Call Webhook

If the assistant has `assistant_end_call_url` configured, a POST request is sent when the call ends.

### Webhook Request

```http
POST /your-webhook-endpoint HTTP/1.1
Content-Type: application/json

{
  "success": true,
  "message": "Call details fetched successfully",
  "data": {
    "room_name": "550e8400-e29b-41d4-a716-446655440000_abc123",
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Agent",
    "to_number": "+15550200000",
    "recording_path": "https://your-bucket.s3.us-east-1.amazonaws.com/recordings/call_abc123.ogg",
    "transcripts": [
      {
        "speaker": "agent",
        "text": "Hello John, how can I help you today?",
        "timestamp": "2024-01-15T10:00:01.000Z"
      },
      {
        "speaker": "user",
        "text": "I need help with my order.",
        "timestamp": "2024-01-15T10:00:05.000Z"
      },
      {
        "speaker": "agent",
        "text": "I'd be happy to help. What's your order number?",
        "timestamp": "2024-01-15T10:00:08.000Z"
      }
    ],
    "started_at": "2024-01-15T10:00:00.000Z",
    "ended_at": "2024-01-15T10:05:30.000Z",
    "call_duration_minutes": 5.5
  }
}
```

### Webhook Payload Schema

| Field                          | Type    | Description                                |
| :----------------------------- | :------ | :----------------------------------------- |
| `success`                      | boolean | Always `true` for webhook notifications.   |
| `message`                      | string  | Status message.                            |
| `data`                         | object  | Complete call details.                     |
| `data.room_name`               | string  | The LiveKit room name.                     |
| `data.assistant_id`            | string  | ID of the assistant used.                  |
| `data.assistant_name`          | string  | Name of the assistant.                     |
| `data.to_number`               | string  | Phone number that was called.              |
| `data.recording_path`          | string  | S3 URL of the call recording (if enabled). |
| `data.transcripts`             | array   | List of conversation messages.             |
| `data.transcripts[].speaker`   | string  | Who spoke (`agent` or `user`).             |
| `data.transcripts[].text`      | string  | The transcribed text.                      |
| `data.transcripts[].timestamp` | string  | ISO 8601 timestamp.                        |
| `data.started_at`              | string  | Call start time (ISO 8601).                |
| `data.ended_at`                | string  | Call end time (ISO 8601).                  |
| `data.call_duration_minutes`   | number  | Total call duration in minutes.            |

## Current Runtime Payload Shape

The webhook payload is generated from the stored call record and currently includes:

- `room_name`
- `assistant_id`
- `assistant_name`
- `to_number`
- `recording_path`
- `transcripts`
- `started_at`
- `ended_at`
- `call_duration_minutes`

Fields like `from_number` or custom `metadata` are not currently included by runtime unless they are persisted into the call record model.

### Quick Test with curl

```bash
curl -X POST "https://your-webhook-url" \
  -H "Content-Type: application/json" \
  -d '{
    "success": true,
    "message": "Call details fetched successfully",
    "data": {
      "room_name": "550e8400-e29b-41d4-a716-446655440000_abc123",
      "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
      "assistant_name": "Support Agent",
      "to_number": "+15550200000",
      "recording_path": "https://your-bucket.s3.us-east-1.amazonaws.com/recordings/call_abc123.ogg",
      "transcripts": [
        {
          "speaker": "agent",
          "text": "Hello John, how can I help you today?",
          "timestamp": "2024-01-15T10:00:01.000Z"
        },
        {
          "speaker": "user",
          "text": "I need help with my order.",
          "timestamp": "2024-01-15T10:00:05.000Z"
        }
      ],
      "started_at": "2024-01-15T10:00:00.000Z",
      "ended_at": "2024-01-15T10:05:30.000Z",
      "call_duration_minutes": 5.5
    }
  }'
```

### Webhook Response

Your webhook endpoint should return a `200 OK` response. The response body is not processed.

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"received": true}
```

!!! warning "Important"

    - Webhooks are sent **after** the call ends and recording/transcript are saved
    - Current runtime sends a single webhook request with a 10s timeout
    - Current runtime does not treat non-2xx HTTP status as a delivery failure
    - Current runtime does not parse webhook response body
    - Ensure your webhook endpoint responds quickly (< 10 seconds)
    - Store the `room_name` to correlate with call initiation
