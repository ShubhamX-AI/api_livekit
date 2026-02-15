# Assistant Management

This section covers the management of AI assistants, including creation, updates, and deletion.

## Create Assistant

Create a new AI assistant configuration.

- **URL**: `/assistant/create`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_name` | string | Yes | The name of the assistant. |
| `assistant_description` | string | Yes | A description of the assistant. |
| `assistant_prompt` | string | Yes | The system prompt for the assistant. |
| `assistant_tts_model` | string | Yes | The TTS provider. One of `cartesia` or `sarvam`. |
| `assistant_tts_config` | object | Yes | The TTS configuration object (see below). |
| `assistant_start_instruction` | string | No | Instruction for the assistant to follow when the call starts. |
| `assistant_end_call_url` | string | No | URL to hit when the call ends. |

### TTS Configuration

**Cartesia Configuration (`assistant_tts_model`: "cartesia")**

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `voice_id` | string | Yes | The Cartesia voice ID (UUID). |

**Sarvam Configuration (`assistant_tts_model`: "sarvam")**

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `speaker` | string | Yes | The Sarvam speaker identifier (e.g., "meera"). |
| `target_language_code` | string | No | BCP-47 language code (default "bn-IN"). |

### Example

```bash
curl -X POST "http://localhost:8000/assistant/create" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "assistant_name": "Support Bot",
           "assistant_description": "First line of support",
           "assistant_prompt": "You are a helpful customer support agent.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
           }
         }'
```

```json
{
  "success": true,
  "message": "Assistant created successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Bot"
  }
}
```

## List Assistants

List all active assistants created by the current user.

- **URL**: `/assistant/list`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X GET "http://localhost:8000/assistant/list" \
     -H "x-api-key: <your_api_key>"
```

## Get Assistant Details

Fetch detailed information about a specific assistant.

- **URL**: `/assistant/details/{assistant_id}`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X GET "http://localhost:8000/assistant/details/550e8400-e29b-41d4-a716-446655440000" \
     -H "x-api-key: <your_api_key>"
```

## Update Assistant

Update the configuration of an existing assistant.

- **URL**: `/assistant/update/{assistant_id}`
- **Method**: `PATCH`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

Only provide the fields you want to update. Fields are the same as in "Create Assistant".
**Note**: If updating `assistant_tts_model` and `assistant_tts_config`, both should ideally be updated together to ensure consistency.

### Example

```bash
curl -X PATCH "http://localhost:8000/assistant/update/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "assistant_name": "Updated Support Bot",
           "assistant_tts_model": "sarvam",
           "assistant_tts_config": {
             "speaker": "meera",
             "target_language_code": "hi-IN"
           }
         }'
```

## Delete Assistant

Soft-delete an assistant.

- **URL**: `/assistant/delete/{assistant_id}`
- **Method**: `DELETE`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X DELETE "http://localhost:8000/assistant/delete/550e8400-e29b-41d4-a716-446655440000" \
     -H "x-api-key: <your_api_key>"
```
