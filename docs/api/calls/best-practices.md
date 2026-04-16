# Best Practices

### Phone Number Formatting

Always use E.164 format:

- ✅ `+15550100000` (US number)
- ✅ `+911234567890` (India number)
- ❌ `555-010-0000` (missing country code)
- ❌ `(555) 010-0000` (parentheses and spaces)

### Metadata Usage

Use metadata for:

- Customer identification
- Campaign tracking
- Context for the assistant
- Post-call analytics

### Queue-Aware Client Design

Treat outbound calling as a two-phase flow:

1. Queue acceptance: `POST /call/outbound` returns `202` with `queue_id`
2. Call lifecycle: once dispatched, the call continues through call logs and webhooks

Recommended client behavior:

- Persist the `queue_id` immediately after the API responds
- Poll `/call/queue/{queue_id}` only for short-term dispatch visibility
- Use the end-call webhook as the source of truth for final outcomes
- Show users clear states such as "queued", "dialing", and "completed/failed" instead of assuming immediate call start

### Error Handling

Common errors and how to handle them:

| Error                     | Cause              | Solution                                |
| :------------------------ | :----------------- | :-------------------------------------- |
| `400` Invalid number      | Wrong format       | Ensure E.164 format                     |
| `404` Assistant not found | Wrong ID           | Verify assistant exists and is active   |
| `404` Trunk not found     | Wrong ID           | Verify trunk exists and belongs to user |
| `404` Queue item not found | Wrong `queue_id` or different owner | Verify you are polling the correct queue item with the same API key owner |
| `500` Provider error      | SIP provider issue | Check provider status and credentials   |

### Call Hold Behavior (Exotel)

When a call is placed on hold via Exotel:

- The agent detects hold instantly through SIP re-INVITE signaling.
- All agent activity is suppressed — no filler words, no silence reprompts, no transcript processing.
- Any in-progress agent speech is immediately interrupted.
- When the call resumes, the agent returns to normal operation automatically.
- This prevents the agent from responding to hold music or generating spurious responses.

!!! note "Provider coverage"
    Hold detection currently works for **Exotel only**. Twilio calls do not have hold detection — if a Twilio call is placed on hold, the agent may respond to hold music.

---

## Next Steps

After triggering a call:

1. **Store the `queue_id`** for dispatch tracking
2. **Poll queue status** until the item becomes `dispatched` or `failed`
3. **Listen for webhook** at your configured endpoint (if set)
4. **Check call recording** in your S3 bucket (if enabled)
5. **Analyze transcripts** for quality assurance
