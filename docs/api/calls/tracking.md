# Call Status Tracking

The `room_name` returned in the response is your unique identifier for the call. You can use this to:

1. **Query call details** from your database (if you store them)
2. **Correlate webhook** notifications with the original call
3. **Monitor active calls** via LiveKit APIs

### Room Name Format

```
{assistant_id}_{unique_suffix}
```

Example: `550e8400-e29b-41d4-a716-446655440000_abc123def456`
