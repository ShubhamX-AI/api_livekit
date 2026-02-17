# Assistant Management

This section covers the management of AI assistants, including creation, updates, and deletion.

## Overview

Assistants are AI agents configured with specific prompts, TTS (Text-to-Speech) settings, and capabilities. Each assistant can have tools attached to extend its functionality.

## Create Assistant

Create a new AI assistant configuration.

- **URL**: `/assistant/create`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field                         | Type   | Required | Description                                                                       |
| :---------------------------- | :----- | :------- | :-------------------------------------------------------------------------------- |
| `assistant_name`              | string | Yes      | The name of the assistant (1-100 characters).                                     |
| `assistant_description`       | string | Yes      | A description of the assistant.                                                   |
| `assistant_prompt`            | string | Yes      | The system prompt that defines the assistant's behavior.                          |
| `assistant_tts_model`         | string | Yes      | The TTS provider. One of `cartesia` or `sarvam`.                                  |
| `assistant_tts_config`        | object | Yes      | The TTS configuration object (see below).                                         |
| `assistant_start_instruction` | string | No       | Instruction for the assistant to speak when the call starts (max 200 characters). |
| `assistant_end_call_url`      | string | No       | URL to POST call details when the call ends.                                      |

### TTS Configuration

=== "Cartesia Configuration"

    Use this when `assistant_tts_model` is set to `"cartesia"`.

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `voice_id` | string | Yes | The Cartesia voice ID (UUID format). |
    | `api_key` | string | No | Optional Cartesia API key. If not provided, the system's default key will be used. |

=== "Sarvam Configuration"

    Use this when `assistant_tts_model` is set to `"sarvam"`.

    | Field | Type | Required | Description |
    | :--- | :--- | :--- | :--- |
    | `speaker` | string | Yes | The Sarvam speaker identifier (e.g., "meera", "arvind"). |
    | `target_language_code` | string | No | BCP-47 language code (default: "bn-IN"). |
    | `api_key` | string | No | Optional Sarvam API key. If not provided, the system's default key will be used. |

### Response Schema

| Field                 | Type    | Description                                 |
| :-------------------- | :------ | :------------------------------------------ |
| `success`             | boolean | Indicates if the operation was successful.  |
| `message`             | string  | Human-readable success message.             |
| `data`                | object  | Contains the created assistant details.     |
| `data.assistant_id`   | string  | Unique identifier for the assistant (UUID). |
| `data.assistant_name` | string  | The name of the assistant.                  |

### HTTP Status Codes

| Code | Description                                                       |
| :--- | :---------------------------------------------------------------- |
| 200  | Success - Assistant created successfully.                         |
| 400  | Bad Request - Invalid input data or mismatched TTS configuration. |
| 401  | Unauthorized - Invalid or missing Bearer token.                   |
| 500  | Server Error - Internal server error.                             |

### Example: Cartesia TTS

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
         -d '{
           "assistant_name": "Support Bot",
           "assistant_description": "First line of support",
           "assistant_prompt": "You are a helpful customer support agent.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275",
             "api_key": "your_custom_cartesia_api_key"
           }
         }'
```

**Response:**

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

### Example: Sarvam TTS

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
         -d '{
           "assistant_name": "Hindi Support",
           "assistant_description": "Hindi speaking support agent",
           "assistant_prompt": "You are a helpful assistant who speaks Hindi.",
           "assistant_tts_model": "sarvam",
           "assistant_tts_config": {
             "speaker": "meera",
             "target_language_code": "hi-IN",
             "api_key": "your_custom_sarvam_api_key"
           }
         }'
```

### Example: With Start Instruction

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/assistant/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_name": "Sales Agent",
           "assistant_description": "Outbound sales representative",
           "assistant_prompt": "You are a friendly sales agent.",
           "assistant_tts_model": "cartesia",
           "assistant_tts_config": {
             "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
           },
           "assistant_start_instruction": "Hello! I'm calling from Acme Corp. How are you today?",
           "assistant_end_call_url": "https://api.example.com/call-ended"
         }'
```

---

## List Assistants

List all active assistants created by the current user.

- **URL**: `/assistant/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Response Schema

| Field                               | Type    | Description                                  |
| :---------------------------------- | :------ | :------------------------------------------- |
| `success`                           | boolean | Indicates if the operation was successful.   |
| `message`                           | string  | Human-readable success message.              |
| `data`                              | array   | List of assistant objects.                   |
| `data[].assistant_id`               | string  | Unique identifier for the assistant.         |
| `data[].assistant_name`             | string  | The name of the assistant.                   |
| `data[].assistant_tts_model`        | string  | The TTS provider used.                       |
| `data[].assistant_created_by_email` | string  | Email of the user who created the assistant. |
| `data[].assistant_created_at`       | string  | ISO 8601 timestamp of creation.              |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - List retrieved successfully.          |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/list" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Assistants retrieved successfully",
  "data": [
    {
      "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
      "assistant_name": "Support Bot",
      "assistant_tts_model": "cartesia",
      "assistant_created_by_email": "admin@example.com",
      "assistant_created_at": "2024-01-15T10:00:00.000000"
    }
  ]
}
```

---

## Get Assistant Details

Fetch detailed information about a specific assistant.

- **URL**: `/assistant/details/{assistant_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter      | Type   | Description                |
| :------------- | :----- | :------------------------- |
| `assistant_id` | string | The UUID of the assistant. |

### Response Schema

| Field                              | Type    | Description                                |
| :--------------------------------- | :------ | :----------------------------------------- |
| `success`                          | boolean | Indicates if the operation was successful. |
| `message`                          | string  | Human-readable success message.            |
| `data`                             | object  | Complete assistant configuration.          |
| `data.assistant_id`                | string  | Unique identifier for the assistant.       |
| `data.assistant_name`              | string  | The name of the assistant.                 |
| `data.assistant_description`       | string  | The description of the assistant.          |
| `data.assistant_prompt`            | string  | The system prompt.                         |
| `data.assistant_tts_model`         | string  | The TTS provider.                          |
| `data.assistant_tts_config`        | object  | The TTS configuration object.              |
| `data.assistant_start_instruction` | string  | The start instruction (if set).            |
| `data.assistant_end_call_url`      | string  | The webhook URL (if set).                  |
| `data.tool_ids`                    | array   | List of attached tool IDs.                 |
| `data.assistant_created_at`        | string  | ISO 8601 timestamp of creation.            |
| `data.assistant_updated_at`        | string  | ISO 8601 timestamp of last update.         |

### HTTP Status Codes

| Code | Description                                          |
| :--- | :--------------------------------------------------- |
| 200  | Success - Assistant details retrieved.               |
| 401  | Unauthorized - Invalid or missing Bearer token.      |
| 404  | Not Found - Assistant does not exist or is inactive. |
| 500  | Server Error - Internal server error.                |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/details/550e8400-e29b-41d4-a716-446655440000" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Assistant details retrieved successfully",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_name": "Support Bot",
    "assistant_description": "First line of support",
    "assistant_prompt": "You are a helpful customer support agent.",
    "assistant_tts_model": "cartesia",
    "assistant_tts_config": {
      "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
    },
    "assistant_start_instruction": null,
    "assistant_end_call_url": null,
    "tool_ids": [],
    "assistant_created_at": "2024-01-15T10:00:00.000000",
    "assistant_updated_at": "2024-01-15T10:00:00.000000"
  }
}
```

---

## Update Assistant

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
           }
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

---

## Delete Assistant

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

---

## Using Placeholders

Both `assistant_prompt` and `assistant_start_instruction` support dynamic placeholders that are replaced at call time using the `metadata` field in the outbound call request.

### Syntax

Use `{{key}}` syntax to define placeholders:

```json
{
  "assistant_prompt": "Hello {{name}}, you are calling from {{company}}. How can I help?",
  "assistant_start_instruction": "Hi {{name}}, this is {{agent_name}} from {{company}}."
}
```

### Triggering with Metadata

When triggering an outbound call, provide the values:

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "trunk_id": "ST_...",
           "to_number": "+15550200000",
           "call_service": "twilio",
           "metadata": {
             "name": "John Doe",
             "company": "Acme Corp",
             "agent_name": "Sarah"
           }
         }'
```

!!! tip "Best Practice"

    Always provide default values in your prompts for cases where metadata might be missing:
    ```json
    {
      "assistant_prompt": "Hello {{name|there}}, welcome to {{company|our service}}!"
    }
    ```
