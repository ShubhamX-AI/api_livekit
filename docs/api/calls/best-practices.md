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

### Error Handling

Common errors and how to handle them:

| Error                     | Cause              | Solution                                |
| :------------------------ | :----------------- | :-------------------------------------- |
| `400` Invalid number      | Wrong format       | Ensure E.164 format                     |
| `404` Assistant not found | Wrong ID           | Verify assistant exists and is active   |
| `404` Trunk not found     | Wrong ID           | Verify trunk exists and belongs to user |
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

1. **Store the room_name** for future reference
2. **Listen for webhook** at your configured endpoint (if set)
3. **Check call recording** in your S3 bucket (if enabled)
4. **Analyze transcripts** for quality assurance
