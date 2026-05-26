# Generate Web Call Token

Create a LiveKit room and return a participant token for browser or mobile web calls.

- **URL**: `/web_call/get_token`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Assistant ID to run in the generated room. |
| `metadata` | object | No | Optional key-value data injected into assistant placeholders. |
| `text_only` | boolean | No | Default `false`. When `true`, the session runs as a text chat: no microphone capture, no TTS synthesis, no LiveKit Egress recording. Only the LLM and the `lk.chat` topic are used. Pipeline-mode assistants only — realtime-mode assistants return 400. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates whether token creation succeeded. |
| `message` | string | Human-readable status message. |
| `data` | object | Generated room and access token payload. |
| `data.room_name` | string | Unique LiveKit room created for this web call. |
| `data.token` | string | Participant access token for joining the room. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - Token generated successfully. |
| 400 | Bad Request - `text_only: true` requested for a realtime-mode assistant. |
| 422 | Validation Error - Invalid request body. |
| 401 | Unauthorized - Invalid or missing Bearer token. |
| 404 | Not Found - Assistant not found for the authenticated user. |
| 500 | Server Error - Internal error while generating the token. |

### Frontend Text + Voice Usage

Web calls support both typed chat and microphone audio in the same room.

Use the standard LiveKit text stream topic `lk.chat`:

```ts
import { useLocalParticipant } from "@livekit/components-react";

await localParticipant.sendText("Hello", { topic: "lk.chat" });
```

The assistant will process this text input and respond normally while audio input/output continues to work in parallel.

### Text-Only Mode (`text_only: true`)

For pure chatbot use cases (no voice on either side), set `"text_only": true` in the request body. The server then:

- Disables microphone capture (`audio_input=false`) and assistant audio playback (`audio_output=false`).
- Skips TTS synthesis entirely — no Cartesia / Sarvam / ElevenLabs / Mistral characters are billed.
- Skips STT (Sarvam Saras v3 parallel STT and OpenAI side-channel transcription are both off — there is no audio to transcribe).
- Skips LiveKit Egress recording — no S3 storage cost, `CallRecord.recording_egress_id` and `recording_path` stay `null`.
- Disables voice-only features: filler words, silence reprompts, background sound, thinking sound.

The LLM (`gpt-realtime-1.5` in pipeline mode) still runs and emits text. Replies are published back on the same `lk.chat` topic as transcription text — the client listens to that topic for both directions.

**Constraint:** only pipeline-mode assistants are supported. Realtime-mode assistants (Gemini realtime / OpenAI realtime bundling STT+LLM+TTS) return HTTP 400 because their audio model has no clean text-only path.

```ts
// Client receives agent replies on the same topic
room.registerTextStreamHandler("lk.chat", async (reader) => {
  const text = await reader.readAll();
  console.log("agent:", text);
});
```

### Example Request — Voice + Text Web Call

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/get_token" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "metadata": {
             "name": "John Doe",
             "plan": "premium"
           }
         }'
```

### Example Request — Text-Only Chat

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/web_call/get_token" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "metadata": {"name": "John Doe"},
           "text_only": true
         }'
```

### Example Response

```json
{
  "success": true,
  "message": "Token generated successfully",
  "data": {
    "room_name": "550e8400-e29b-41d4-a716-446655440000_ab12cd34",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```
