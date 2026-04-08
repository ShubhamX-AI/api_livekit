# Call Status Tracking

The `room_name` returned by `/call/outbound` or `/web_call/get_token` is your unique identifier for the call.

### Room Name Format

```
{assistant_id}_{unique_suffix}
```

Example: `550e8400-e29b-41d4-a716-446655440000_abc123def456`

---

## How to Track a Call

### Option 1 — End-Call Webhook (recommended)

Configure `assistant_end_call_url` on the assistant. When a call reaches a terminal state, the platform POSTs the full call record, including both actual duration and backend-calculated billable duration, to that URL.

See [End Call Webhook](webhook.md) for the complete payload contract.

### Option 2 — Query Call Logs

Use `GET /assistant/call-logs/{assistant_id}` to look up past and current call records.

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/call-logs/ASSISTANT_ID?limit=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Filter by room name to retrieve a specific call:

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/assistant/call-logs/ASSISTANT_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Then match the desired `room_name` in the returned `logs` array.

Full query parameters (pagination, date range, sort) are documented in [Call Logs](../assistant/logs.md).

---

## Call Status Values

| Status | Meaning |
| :--- | :--- |
| `initiated` | Call setup started |
| `answered` | Call was answered and media path is ready |
| `completed` | Call ended after an active session |
| `busy` | Callee line was busy |
| `no_answer` | Callee did not answer in time |
| `rejected` | Call was explicitly rejected |
| `cancelled` | Setup cancelled before answer |
| `unreachable` | Destination number unreachable |
| `timeout` | Setup timed out |
| `failed` | Generic setup or runtime failure |

!!! info "Exotel async calls"

    For Exotel outbound calls (`202 Accepted`), the call record starts as `initiated`.
    The terminal status (`completed`, `busy`, `no_answer`, etc.) is set only after the bridge resolves the outcome.
    Use the webhook or poll call logs to detect the final state.
