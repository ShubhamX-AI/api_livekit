# Using Placeholders

Both `assistant_prompt` and `assistant_start_instruction` support `{{...}}` placeholders that are filled in at call time, for outbound and inbound calls alike.

## The One Rule

> **Your payload's shape is the placeholder path.**

Send a value flat, and you reference it flat. Nest it, and you reference it with a dot. Nothing is forced on you, and the rule is the same in both directions.

| You send | You write |
| :--- | :--- |
| `{"name": "John"}` | `{{name}}` |
| `{"customer": {"name": "John"}}` | `{{customer.name}}` |
| `{"account": {"owner": {"name": "John"}}}` | `{{account.owner.name}}` |
| `{"tags": ["vip", "renewal"]}` | `{{tags.0}}` |

Where that payload comes from is the only difference between the two call directions:

- **Outbound** — the `metadata` object in your `POST /call/outbound` request body.
- **Inbound** — the entire JSON body your context-strategy webhook returns.

Everything below follows from those two sentences.

## Outbound Calls

Variables travel in the `metadata` field. It exists because `metadata` has to share the request body with `to_number`, `trunk_id`, and the rest — the field name itself is never part of a placeholder.

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

Template:

```json
{
  "assistant_prompt": "You are {{agent_name}} from {{company}}. The customer is {{name}}, on the {{plan}} plan.",
  "assistant_start_instruction": "Hi {{name}}, this is {{agent_name}} from {{company}}."
}
```

Renders as:

```
You are Sarah from Acme Corp. The customer is John Doe, on the Enterprise plan.
Hi John Doe, this is Sarah from Acme Corp.
```

### Nested Outbound Metadata

Group related values if you prefer — the placeholders follow whatever structure you send.

```json
{
  "metadata": {
    "customer": { "name": "John Doe", "plan": "Enterprise" },
    "agent": { "name": "Sarah" }
  }
}
```

```json
{
  "assistant_prompt": "You are {{agent.name}}. The customer is {{customer.name}} on {{customer.plan}}."
}
```

```
You are Sarah. The customer is John Doe on Enterprise.
```

Note that `{{name}}` resolves to nothing here — the value is nested, so the placeholder must be too. Pick one style and stay with it.

## Inbound Calls

Variables come from the webhook configured on the number's [inbound context strategy](../inbound-context-strategy/index.md). Whatever JSON object your webhook returns *is* the payload — there is no wrapper key to add.

Webhook returns:

```json
{
  "customer_name": "John Doe",
  "ticket_id": "TCK-1234",
  "plan": "Enterprise"
}
```

Template:

```json
{
  "assistant_prompt": "The caller is {{customer_name}} on the {{plan}} plan. Open ticket: {{ticket_id}}.",
  "assistant_start_instruction": "Welcome back {{customer_name}}."
}
```

```
The caller is John Doe on the Enterprise plan. Open ticket: TCK-1234.
Welcome back John Doe.
```

### Nested Inbound Response

```json
{
  "customer": { "name": "John Doe", "plan": "Enterprise" },
  "ticket": { "id": "TCK-1234", "status": "open" }
}
```

```json
{
  "assistant_prompt": "Caller {{customer.name}} ({{customer.plan}}) has ticket {{ticket.id}}, currently {{ticket.status}}."
}
```

```
Caller John Doe (Enterprise) has ticket TCK-1234, currently open.
```

### If Your Webhook Wraps Its Response

A webhook that returns a `context` object is not a special case — `context` is read as an ordinary key, so it simply becomes part of the path:

```json
{ "context": { "customer_name": "John Doe" } }
```

```json
{ "assistant_prompt": "Hello {{context.customer_name}}." }
```

This is why prompts written against older `{{context.*}}` examples keep working with no change. If you would rather write `{{customer_name}}`, drop the wrapper from your webhook response.

## Call Metadata: the `call.*` Namespace

Alongside your own variables, the platform's own call fields are always available — both flat and under a `call.` prefix.

Inbound calls provide:

| Placeholder | Meaning |
| :--- | :--- |
| `{{call.call_type}}` | `inbound` |
| `{{call.service}}` | Inbound provider, currently `exotel` |
| `{{call.assistant_id}}` | Assistant resolved from the number mapping |
| `{{call.assistant_name}}` | Assistant name |
| `{{call.inbound_id}}` | Inbound mapping identifier |
| `{{call.inbound_context_strategy_id}}` | Strategy attached to the number, if any |
| `{{call.inbound_number}}` | Normalized number that was dialed |
| `{{call.caller_number}}` | Caller's number |

Outbound calls provide `{{call.to_number}}` and `{{call.call_service}}`, plus everything you put in `metadata` (so `{{call.name}}` and `{{name}}` are the same value).

### When a Name Collides

Your variables are merged after the call metadata, so if you send a key that shares a name with a platform field, yours wins the bare placeholder:

| Source | `caller_number` |
| :--- | :--- |
| Platform call metadata | `+919876543210` |
| Your webhook response | `+911111111111` |

```
{{caller_number}}       renders  +911111111111
{{call.caller_number}}  renders  +919876543210
```

`{{call.*}}` is never overwritten, so it is the reliable way to read a platform field. To avoid the shadowing entirely, steer clear of the reserved names — the eight inbound fields listed above, and `to_number` / `call_service` on outbound.

## Missing Values

Missing keys render as an empty string. There is no error and no `if/else`.

```
Hello {{customer_name}}, welcome back.
```

becomes `Hello , welcome back.` when the value is absent. Two ways to avoid that:

**Keep optional values out of the opening line.**

```
Welcome back. I can see you're calling from {{call.caller_number}}.
```

**Use a section block.** `{{#key}}...{{/key}}` renders the inner text only when the key is present and non-empty:

```
I have your account pulled up{{#customer_name}} for {{customer_name}}{{/customer_name}}. How can I help you today?
```

With a name: `I have your account pulled up for John Doe. How can I help you today?`
Without: `I have your account pulled up. How can I help you today?`

Sections work on nested paths too — `{{#customer.plan}}...{{/customer.plan}}`.

## Quick Reference

| Situation | Behavior |
| :--- | :--- |
| Flat value | `{{key}}` |
| Nested value | `{{parent.child}}`, to any depth |
| Array element | `{{list.0}}` |
| Missing key | Empty string |
| Optional text | `{{#key}}...{{/key}}` |
| Platform call fields | `{{call.*}}`, never overwritten |
| Your key shadows a platform key | Yours wins the bare form; use `{{call.*}}` for the platform value |
| Inbound lookup fails or is not configured | Prompt still renders; those placeholders are empty and the call proceeds |
