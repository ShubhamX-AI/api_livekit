# Tool Management

Tools allow your assistant to perform actions or fetch data. This section covers creating, updating, and managing tools.

## Create Tool

Define a new tool that can be used by your assistants.

- **URL**: `/tool/create`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `tool_name` | string | Yes | Snake_case name (e.g., `lookup_weather`). |
| `tool_description` | string | Yes | Description for the LLM explaining what the tool does. |
| `tool_parameters` | array | No | List of parameters (see below). |
| `tool_execution_type` | string | Yes | `webhook` or `static_return`. |
| `tool_execution_config` | object | Yes | Config for execution (e.g., URL for webhook). |

### Tool Parameter Schema

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | Yes | Parameter name. |
| `type` | string | Yes | `string`, `number`, `boolean`, `object`, or `array`. |
| `description` | string | No | Description for the LLM. |
| `required` | boolean | No | whether the parameter is mandatory (default `true`). |
| `enum` | array | No | Allowed values (for string types). |

### Example

```bash
curl -X POST "http://localhost:8000/tool/create" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "tool_name": "get_weather",
           "tool_description": "Get current weather for a location",
           "tool_parameters": [
             {
               "name": "location",
               "type": "string",
               "description": "City and state, e.g. San Francisco, CA",
               "required": true
             }
           ],
           "tool_execution_type": "webhook",
           "tool_execution_config": {
             "url": "https://api.example.com/weather-webhook"
           }
         }'
```

```json
{
  "success": true,
  "message": "Tool created successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999",
    "tool_name": "get_weather"
  }
}
```

## List Tools

List all active tools.

- **URL**: `/tool/list`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X GET "http://localhost:8000/tool/list" \
     -H "x-api-key: <your_api_key>"
```

## Get Tool Details

Fetch details for a specific tool.

- **URL**: `/tool/details/{tool_id}`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X GET "http://localhost:8000/tool/details/880e8400-e29b-41d4-a716-446655449999" \
     -H "x-api-key: <your_api_key>"
```

## Update Tool

Update an existing tool.

- **URL**: `/tool/update/{tool_id}`
- **Method**: `PATCH`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Example

```bash
curl -X PATCH "http://localhost:8000/tool/update/880e8400-e29b-41d4-a716-446655449999" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "tool_description": "Updated description for weather tool"
         }'
```

## Delete Tool

Soft-delete a tool. This will also remove the tool from any assistants that are currently using it.

- **URL**: `/tool/delete/{tool_id}`
- **Method**: `DELETE`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X DELETE "http://localhost:8000/tool/delete/880e8400-e29b-41d4-a716-446655449999" \
     -H "x-api-key: <your_api_key>"
```

## Attach Tools to Assistant

Enable a set of tools for a specific assistant.

- **URL**: `/tool/attach/{assistant_id}`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `tool_ids` | array | Yes | List of tool IDs to attach. |

### Example

```bash
curl -X POST "http://localhost:8000/tool/attach/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
         }'
```

## Detach Tools from Assistant

Remove a set of tools from a specific assistant.

- **URL**: `/tool/detach/{assistant_id}`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `tool_ids` | array | Yes | List of tool IDs to detach. |

### Example

```bash
curl -X POST "http://localhost:8000/tool/detach/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
         }'
```
