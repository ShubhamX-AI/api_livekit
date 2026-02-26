# Webhook Payload Format

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
