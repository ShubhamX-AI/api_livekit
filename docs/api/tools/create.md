# Create Tool

Define a new tool that can be used by your assistants.

- **URL**: `/tool/create`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field                   | Type   | Required | Description                                                                 |
| :---------------------- | :----- | :------- | :-------------------------------------------------------------------------- |
| `tool_name`             | string | Yes      | Snake_case name, e.g., `lookup_weather` (must match `^[a-z][a-z0-9_]*$`). |
| `tool_description`      | string | Yes      | Description for the LLM explaining what the tool does (1-500 characters).   |
| `tool_parameters`       | array  | No       | List of parameters (see schema below).                                      |
| `tool_execution_type`   | string | Yes      | `webhook` or `static_return`.                                               |
| `tool_execution_config` | object | Yes      | Configuration for execution (see examples below).                           |

### Tool Parameter Schema

| Field         | Type    | Required | Description                                                     |
| :------------ | :------ | :------- | :-------------------------------------------------------------- |
| `name`        | string  | Yes      | Parameter name.                                                 |
| `type`        | string  | Yes      | Data type: `string`, `number`, `boolean`, `object`, or `array`. |
| `description` | string  | No       | Description for the LLM.                                        |
| `required`    | boolean | No       | Whether the parameter is mandatory (default: `true`).           |
| `enum`        | array   | No       | Allowed values (only for string types).                         |

!!! note "Strict schemas, and what turns them off"
    This applies to **`cascade` mode only** — that is the mode whose LLM validates tool
    schemas. In `pipeline` and `realtime` mode the same tool is sent to the Realtime API,
    which has no strict mode; the notes below change nothing there.

    In cascade, OpenAI validates a tool's schema strictly by default: every parameter must be
    required, and every `object` and `array` must be fully described. A tool whose parameters
    are all required scalars (`string`, `number`, `boolean`) is sent strict, so the model's
    arguments are guaranteed to match it.

    A tool loses that guarantee — the runtime sends `strict: false` for it, and logs which
    parameter caused it — when it has any **optional** parameter, or any `object` / `array`
    parameter (this API has no way to describe an object's fields or an array's items, and
    strict mode requires both). The tool still works; the model may just pass arguments the
    schema does not describe. Prefer required scalar parameters, and flatten an object into
    separate fields, when you want the strict guarantee.

    Keep `tool_name` at 64 characters or fewer. The field accepts 100, but OpenAI rejects
    anything longer than 64 — such a tool is skipped at call time (logged), and the rest of
    the assistant's tools still load.

    === "Strict (all parameters required, scalars only)"

        ```json title="What you create"
        {
          "tool_name": "lookup_weather",
          "tool_description": "Get current weather for a location",
          "tool_parameters": [
            { "name": "location", "type": "string", "description": "City name", "required": true },
            { "name": "unit", "type": "string", "enum": ["c", "f"], "required": true }
          ]
        }
        ```

        ```json title="What cascade sends to OpenAI"
        {
          "type": "function",
          "name": "lookup_weather",
          "description": "Get current weather for a location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": { "type": "string", "description": "City name" },
              "unit": { "type": "string", "enum": ["c", "f"] }
            },
            "required": ["location", "unit"],
            "additionalProperties": false
          }
        }
        ```

        No `strict` key means the API default — strict — applies. Arguments are guaranteed
        to match the schema.

    === "Relaxed (one optional parameter)"

        ```json title="What you create"
        {
          "tool_name": "lookup_weather",
          "tool_description": "Get current weather for a location",
          "tool_parameters": [
            { "name": "location", "type": "string", "required": true },
            { "name": "unit", "type": "string", "enum": ["c", "f"], "required": false }
          ]
        }
        ```

        ```json title="What cascade sends to OpenAI"
        {
          "type": "function",
          "name": "lookup_weather",
          "description": "Get current weather for a location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": { "type": "string" },
              "unit": { "type": "string", "enum": ["c", "f"] }
            },
            "required": ["location"],
            "additionalProperties": false
          },
          "strict": false
        }
        ```

        ```text title="Logged once at call start"
        INFO  Tool 'lookup_weather': strict schema off (unit is optional). Arguments are no
              longer guaranteed to match the schema.
        ```

        Without the `strict: false`, OpenAI rejects this schema outright — `required` must
        list every property — and the rejection takes down every LLM turn of the call, not
        just this tool.

    In `pipeline` and `realtime` mode the same tool document produces the same schema
    **without** the `strict` key, because the Realtime API has no such field.

### Execution Config Examples

=== "Webhook Tool"

    For tools that call external HTTP endpoints.

    **Required Fields:**

    | Field | Type | Description |
    | :--- | :--- | :--- |
    | `url` | string | The webhook URL to POST to. |

    **Optional Fields:**

    | Field | Type | Description |
    | :--- | :--- | :--- |
    | `timeout` | number | Request timeout in seconds (default: 10). |
    | `headers` | object | Additional HTTP headers. |

    **Example:**

    ```json
    {
      "tool_name": "lookup_weather",
      "tool_description": "Get current weather information for a given location",
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
        "url": "https://api.weather.com/v1/current",
        "timeout": 5,
        "headers": {
          "Authorization": "Bearer weather_api_token",
          "Content-Type": "application/json"
        }
      }
    }
    ```

=== "Static Return Tool"

    For tools that return a fixed value without external calls.

    **Required Fields:**

    | Field | Type | Description |
    | :--- | :--- | :--- |
    | `value` | any | The static value to return (string, number, boolean, object, or array). |

    **Example:**

    ```json
    {
      "tool_name": "get_support_email",
      "tool_description": "Get the customer support email address",
      "tool_execution_type": "static_return",
      "tool_execution_config": {
        "value": "support@example.com"
      }
    }
    ```

    **Example with Object:**

    ```json
    {
      "tool_name": "get_business_hours",
      "tool_description": "Get the business operating hours",
      "tool_execution_type": "static_return",
      "tool_execution_config": {
        "value": {
          "monday": "9:00 AM - 6:00 PM",
          "tuesday": "9:00 AM - 6:00 PM",
          "wednesday": "9:00 AM - 6:00 PM",
          "thursday": "9:00 AM - 6:00 PM",
          "friday": "9:00 AM - 5:00 PM",
          "saturday": "Closed",
          "sunday": "Closed"
        }
      }
    }
    ```

### Response Schema

| Field            | Type    | Description                                |
| :--------------- | :------ | :----------------------------------------- |
| `success`        | boolean | Indicates if the operation was successful. |
| `message`        | string  | Human-readable success message.            |
| `data`           | object  | Contains the created tool details.         |
| `data.tool_id`   | string  | Unique identifier for the tool (UUID).     |
| `data.tool_name` | string  | The name of the tool.                      |

### HTTP Status Codes

| Code | Description                                                             |
| :--- | :---------------------------------------------------------------------- |
| 200  | Success - Tool created successfully.                                    |
| 400  | Bad Request - Invalid input data (invalid name format, missing fields). |
| 401  | Unauthorized - Invalid or missing Bearer token.                         |
| 500  | Server Error - Internal server error.                                   |

### Complete Example: Weather Webhook Tool

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_name": "lookup_weather",
           "tool_description": "Get current weather information for a given location",
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
             "url": "https://api.weather.com/v1/current",
             "timeout": 5,
             "headers": {
               "Authorization": "Bearer weather_api_token"
             }
           }
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Tool created successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999",
    "tool_name": "lookup_weather"
  }
}
```

### Complete Example: Static Return Tool

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/create" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_name": "get_support_email",
           "tool_description": "Get the customer support email address",
           "tool_execution_type": "static_return",
           "tool_execution_config": {
             "value": "support@example.com"
           }
         }'
```
