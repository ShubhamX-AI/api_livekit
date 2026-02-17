# Tool Management

Tools allow your assistant to perform actions or fetch data during conversations. This section covers creating, updating, and managing tools.

## Overview

Tools are custom functions that extend your assistant's capabilities. When the LLM determines a tool should be called, the system executes it and returns the result to continue the conversation.

### Execution Types

| Type              | Description                       | Use Case                                                     |
| :---------------- | :-------------------------------- | :----------------------------------------------------------- |
| **Webhook**       | HTTP POST request to external URL | Fetch live data (weather, stock prices, user info)           |
| **Static Return** | Return a fixed value              | Provide constant information (support email, business hours) |

---

## Create Tool

Define a new tool that can be used by your assistants.

- **URL**: `/tool/create`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field                   | Type   | Required | Description                                                                 |
| :---------------------- | :----- | :------- | :-------------------------------------------------------------------------- |
| `tool_name`             | string | Yes      | Snake*case name, e.g., `lookup_weather` (must match `^[a-z*][a-z0-9_]\*$`). |
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

---

## List Tools

List all active tools created by the current user.

- **URL**: `/tool/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Response Schema

| Field                        | Type    | Description                                |
| :--------------------------- | :------ | :----------------------------------------- |
| `success`                    | boolean | Indicates if the operation was successful. |
| `message`                    | string  | Human-readable success message.            |
| `data`                       | array   | List of tool objects.                      |
| `data[].tool_id`             | string  | Unique identifier for the tool.            |
| `data[].tool_name`           | string  | The name of the tool.                      |
| `data[].tool_description`    | string  | The description of the tool.               |
| `data[].tool_execution_type` | string  | Either `webhook` or `static_return`.       |
| `data[].tool_created_at`     | string  | ISO 8601 timestamp of creation.            |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Tools retrieved successfully.         |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/tool/list" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tools retrieved successfully",
  "data": [
    {
      "tool_id": "880e8400-e29b-41d4-a716-446655449999",
      "tool_name": "lookup_weather",
      "tool_description": "Get current weather information for a given location",
      "tool_execution_type": "webhook",
      "tool_created_at": "2024-01-15T10:00:00.000000"
    },
    {
      "tool_id": "990e8400-e29b-41d4-a716-446655449888",
      "tool_name": "get_support_email",
      "tool_description": "Get the customer support email address",
      "tool_execution_type": "static_return",
      "tool_created_at": "2024-01-15T11:00:00.000000"
    }
  ]
}
```

---

## Get Tool Details

Fetch details for a specific tool.

- **URL**: `/tool/details/{tool_id}`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter | Type   | Description           |
| :-------- | :----- | :-------------------- |
| `tool_id` | string | The UUID of the tool. |

### Response Schema

| Field                        | Type    | Description                                |
| :--------------------------- | :------ | :----------------------------------------- |
| `success`                    | boolean | Indicates if the operation was successful. |
| `message`                    | string  | Human-readable success message.            |
| `data`                       | object  | Complete tool configuration.               |
| `data.tool_id`               | string  | Unique identifier for the tool.            |
| `data.tool_name`             | string  | The name of the tool.                      |
| `data.tool_description`      | string  | The description of the tool.               |
| `data.tool_parameters`       | array   | List of parameter definitions.             |
| `data.tool_execution_type`   | string  | Either `webhook` or `static_return`.       |
| `data.tool_execution_config` | object  | Execution configuration.                   |
| `data.tool_created_at`       | string  | ISO 8601 timestamp of creation.            |
| `data.tool_updated_at`       | string  | ISO 8601 timestamp of last update.         |

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Tool details retrieved.               |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 404  | Not Found - Tool does not exist or is inactive. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/tool/details/880e8400-e29b-41d4-a716-446655449999" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tool details retrieved successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999",
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
    },
    "tool_created_at": "2024-01-15T10:00:00.000000",
    "tool_updated_at": "2024-01-15T10:00:00.000000"
  }
}
```

---

## Update Tool

Update an existing tool's configuration.

- **URL**: `/tool/update/{tool_id}`
- **Method**: `PATCH`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter | Type   | Description                     |
| :-------- | :----- | :------------------------------ |
| `tool_id` | string | The UUID of the tool to update. |

### Request Body

Only provide the fields you want to update. All fields are optional.

| Field                   | Type   | Description                                        |
| :---------------------- | :----- | :------------------------------------------------- |
| `tool_name`             | string | The new name (must follow snake_case format).      |
| `tool_description`      | string | The new description.                               |
| `tool_parameters`       | array  | New parameter definitions (replaces all existing). |
| `tool_execution_type`   | string | New execution type (`webhook` or `static_return`). |
| `tool_execution_config` | object | New execution configuration.                       |

### Response Schema

| Field          | Type    | Description                                |
| :------------- | :------ | :----------------------------------------- |
| `success`      | boolean | Indicates if the operation was successful. |
| `message`      | string  | Human-readable success message.            |
| `data`         | object  | Contains the updated tool ID.              |
| `data.tool_id` | string  | The ID of the updated tool.                |

### HTTP Status Codes

| Code | Description                                             |
| :--- | :------------------------------------------------------ |
| 200  | Success - Tool updated successfully.                    |
| 400  | Bad Request - Invalid input data or no fields provided. |
| 401  | Unauthorized - Invalid or missing Bearer token.         |
| 404  | Not Found - Tool does not exist.                        |
| 500  | Server Error - Internal server error.                   |

### Example: Update Webhook URL

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/tool/update/880e8400-e29b-41d4-a716-446655449999" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_execution_config": {
             "url": "https://api.new-weather.com/v1/current",
             "timeout": 10,
             "headers": {
               "Authorization": "Bearer new_token"
             }
           }
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Tool updated successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999"
  }
}
```

---

## Delete Tool

Soft-delete a tool. This will also remove the tool from any assistants that are currently using it.

- **URL**: `/tool/delete/{tool_id}`
- **Method**: `DELETE`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter | Type   | Description                     |
| :-------- | :----- | :------------------------------ |
| `tool_id` | string | The UUID of the tool to delete. |

### Response Schema

| Field          | Type    | Description                                |
| :------------- | :------ | :----------------------------------------- |
| `success`      | boolean | Indicates if the operation was successful. |
| `message`      | string  | Human-readable success message.            |
| `data`         | object  | Contains the deleted tool ID.              |
| `data.tool_id` | string  | The ID of the deleted tool.                |

### HTTP Status Codes

| Code | Description                                             |
| :--- | :------------------------------------------------------ |
| 200  | Success - Tool deleted successfully.                    |
| 401  | Unauthorized - Invalid or missing Bearer token.         |
| 404  | Not Found - Tool does not exist or is already inactive. |
| 500  | Server Error - Internal server error.                   |

### Example Request

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/tool/delete/880e8400-e29b-41d4-a716-446655449999" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Tool deleted successfully",
  "data": {
    "tool_id": "880e8400-e29b-41d4-a716-446655449999"
  }
}
```

---

## Attach Tools to Assistant

Enable a set of tools for a specific assistant.

- **URL**: `/tool/attach/{assistant_id}`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter      | Type   | Description                |
| :------------- | :----- | :------------------------- |
| `assistant_id` | string | The UUID of the assistant. |

### Request Body

| Field      | Type  | Required | Description                                         |
| :--------- | :---- | :------- | :-------------------------------------------------- |
| `tool_ids` | array | Yes      | List of tool IDs to attach (at least one required). |

### Response Schema

| Field               | Type    | Description                                |
| :------------------ | :------ | :----------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful. |
| `message`           | string  | Human-readable success message with count. |
| `data`              | object  | Contains attachment details.               |
| `data.assistant_id` | string  | The assistant ID.                          |
| `data.tool_ids`     | array   | Updated list of all attached tool IDs.     |

### HTTP Status Codes

| Code | Description                                         |
| :--- | :-------------------------------------------------- |
| 200  | Success - Tools attached successfully.              |
| 400  | Bad Request - Invalid input (empty tool_ids array). |
| 401  | Unauthorized - Invalid or missing Bearer token.     |
| 404  | Not Found - Assistant or one/more tools not found.  |
| 500  | Server Error - Internal server error.               |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/attach/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Attached 1 tool(s) to assistant",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
  }
}
```

---

## Detach Tools from Assistant

Remove a set of tools from a specific assistant.

- **URL**: `/tool/detach/{assistant_id}`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Path Parameters

| Parameter      | Type   | Description                |
| :------------- | :----- | :------------------------- |
| `assistant_id` | string | The UUID of the assistant. |

### Request Body

| Field      | Type  | Required | Description                                         |
| :--------- | :---- | :------- | :-------------------------------------------------- |
| `tool_ids` | array | Yes      | List of tool IDs to detach (at least one required). |

### Response Schema

| Field               | Type    | Description                                  |
| :------------------ | :------ | :------------------------------------------- |
| `success`           | boolean | Indicates if the operation was successful.   |
| `message`           | string  | Human-readable success message.              |
| `data`              | object  | Contains detachment details.                 |
| `data.assistant_id` | string  | The assistant ID.                            |
| `data.tool_ids`     | array   | Updated list of remaining attached tool IDs. |

### HTTP Status Codes

| Code | Description                                         |
| :--- | :-------------------------------------------------- |
| 200  | Success - Tools detached successfully.              |
| 400  | Bad Request - Invalid input (empty tool_ids array). |
| 401  | Unauthorized - Invalid or missing Bearer token.     |
| 404  | Not Found - Assistant not found.                    |
| 500  | Server Error - Internal server error.               |

### Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/tool/detach/550e8400-e29b-41d4-a716-446655440000" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "tool_ids": ["880e8400-e29b-41d4-a716-446655449999"]
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Detached tool(s) from assistant",
  "data": {
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "tool_ids": []
  }
}
```

---

## Webhook Payload Format

When a tool with `webhook` execution type is called, the system sends the following payload to your webhook URL:

### Request to Webhook

```http
POST /your-webhook-endpoint HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token> (if specified in headers)

{
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
  "room_name": "call-room-123",
  "tool_name": "lookup_weather",
  "parameters": {
    "location": "San Francisco, CA"
  },
  "metadata": {
    "customer_id": "12345"
  }
}
```

### Expected Response

Your webhook should return a JSON response:

```json
{
  "success": true,
  "data": {
    "temperature": 72,
    "condition": "Sunny",
    "location": "San Francisco, CA"
  }
}
```

Or for errors:

```json
{
  "success": false,
  "error": "Location not found"
}
```

!!! tip "Best Practices"

    - **Idempotency**: Webhook calls may be retried on timeout. Ensure your endpoint handles duplicate calls gracefully.
    - **Timeouts**: Default timeout is 10 seconds. Design your webhooks to respond quickly.
    - **Authentication**: Use the `headers` field in `tool_execution_config` to pass API keys securely.
    - **Error Handling**: Always return a valid JSON response, even on errors.

---

## Tool Design Guidelines

### Writing Good Tool Descriptions

The `tool_description` is crucial - it's what the LLM uses to decide when to call your tool:

!!! success "Good Examples"

    ```json
    {
      "tool_description": "Get the current stock price for a given ticker symbol. Use this when the user asks about stock prices, investments, or financial data."
    }
    ```

    ```json
    {
      "tool_description": "Schedule an appointment for the user. Only use this when the user explicitly asks to book, schedule, or make an appointment."
    }
    ```

!!! failure "Bad Examples"

    ```json
    {
      "tool_description": "Weather tool"
    }
    ```

    ```json
    {
      "tool_description": "This function gets weather data from our API and returns it in JSON format"
    }
    ```

### Parameter Design

- **Be specific** with parameter descriptions
- **Use enums** when there are limited valid values
- **Set required appropriately** - only mark truly required fields as required
- **Choose the right type** - use `number` for numeric values, not strings

### Execution Type Selection

| Use Webhook When                | Use Static Return When      |
| ------------------------------- | --------------------------- |
| Data changes frequently         | Information never changes   |
| External API integration needed | No external dependencies    |
| User-specific data required     | Same response for all users |
| Complex business logic          | Simple constant values      |
