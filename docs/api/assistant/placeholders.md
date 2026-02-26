# Using Placeholders

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
