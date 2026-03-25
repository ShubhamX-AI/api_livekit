# Using Placeholders

Both `assistant_prompt` and `assistant_start_instruction` support dynamic placeholders that are rendered at call time.

This applies to both outbound and inbound calls.

### Syntax

Use `{{key}}` syntax to define placeholders:

```json
{
  "assistant_prompt": "Hello {{name}}, you are calling from {{company}}. How can I help?",
  "assistant_start_instruction": "Hi {{name}}, this is {{agent_name}} from {{company}}."
}
```

## Data Sources Available at Render Time

The worker renders templates using:

- Top-level call metadata keys for backward compatibility.
- `call.*` namespace with call metadata.
- Optional `context.*` namespace for inbound caller-context lookup results.

## Backward Compatibility

Older templates like `{{name}}` continue to work.

Recommended for new templates:

- Use `{{call.name}}` for call metadata.
- Use `{{context.customer_name}}` for inbound webhook context.

## Outbound Example (Metadata Only)

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
             "agent_name": "Sarah",
             "plan": "Enterprise"
           }
         }'
```

Template example:

```json
{
  "assistant_prompt": "Hello {{call.name}}, I can see your plan is {{call.plan}}.",
  "assistant_start_instruction": "Hi {{name}}, this is {{agent_name}} from {{company}}."
}
```

## Inbound Example (Call Metadata + Context)

If inbound mapping has an attached context strategy and lookup succeeds, context data becomes available as `context.*`.

See the exact webhook request and response contract in [Inbound Context Strategies](../inbound-context-strategy/index.md#webhook-request-payload).

Template example:

```json
{
  "assistant_prompt": "Hi {{context.customer_name}}, I see your caller number is {{call.caller_number}}.",
  "assistant_start_instruction": "Welcome back {{context.customer_name}}. Your open ticket is {{context.ticket_id}}."
}
```

Possible inbound metadata keys include:

- `call.call_type`
- `call.service`
- `call.assistant_id`
- `call.assistant_name`
- `call.inbound_id`
- `call.inbound_context_strategy_id`
- `call.inbound_number`
- `call.caller_number`

## Optionality and Failure Behavior

If no inbound strategy is attached:

- `context.*` values are unavailable.
- Prompt rendering still runs using metadata.

If lookup fails (timeout/HTTP/invalid response):

- `context.*` values are unavailable for that call.
- The assistant still starts and call handling continues.
- Lookup attempts are visible in activity logs as `inbound_context_lookup`.

!!! tip "Best Practice"

    Missing keys render as empty strings. The template engine does **not** support conditionals (`if/else`). Write prompts that still read naturally when optional fields are absent.

    **Risky** — renders as `Hello , welcome back.` when name is missing:
    ```
    Hello {{context.customer_name}}, welcome back.
    ```

    **Safe** — reads naturally even when name is missing:
    ```
    Welcome back. I can see you're calling from {{call.caller_number}}.
    ```

    **Safe with fallback phrasing** — place the optional value mid-sentence where its absence is less noticeable:
    ```
    I have your account pulled up{{context.customer_name ? " for " + context.customer_name : ""}}. How can I help you today?
    ```

    When in doubt, keep the opening greeting independent of optional context fields and use those fields only in follow-up lines where omission is less noticeable.
