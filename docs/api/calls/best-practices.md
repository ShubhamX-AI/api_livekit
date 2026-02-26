# Best Practices

### Phone Number Formatting

Always use E.164 format:

- ✅ `+15550100000` (US number)
- ✅ `+911234567890` (India number)
- ❌ `555-010-0000` (missing country code)
- ❌ `(555) 010-0000` (parentheses and spaces)

### Rate Limiting

Be aware of your SIP provider's rate limits:

- **Twilio**: Varies by account type
- **Exotel**: Check your plan limits

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

---

## Next Steps

After triggering a call:

1. **Store the room_name** for future reference
2. **Listen for webhook** at your configured endpoint (if set)
3. **Check call recording** in your S3 bucket (if enabled)
4. **Analyze transcripts** for quality assurance
