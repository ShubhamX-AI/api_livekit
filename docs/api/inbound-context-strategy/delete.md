# Delete Inbound Context Strategy

Deactivate a strategy and detach it from active inbound mappings that reference it.

- **URL**: `/inbound_context_strategy/delete/{strategy_id}`
- **Method**: `DELETE`
- **Auth**: `Authorization: Bearer <your_api_key>`

## What Happens

1. The strategy is marked inactive.
2. All active inbound mappings owned by the same user with this `inbound_context_strategy_id` are updated to `null`.

## What Does Not Happen

- Inbound mappings are not deleted.
- Assistant attachments on those mappings are not removed.
- Inbound call routing remains active for those numbers if an assistant is still attached.

## Example Request

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/delete/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>"
```

## Success Response

```json
{
  "success": true,
  "message": "Inbound context strategy deleted successfully",
  "data": {
    "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de"
  }
}
```

## Operational Impact

After deletion, future inbound calls on previously linked mappings continue without inbound context lookup and fall back to default prompt rendering behavior.

## Common Errors

| Code | Reason |
| :--- | :--- |
| `401` | Invalid or missing API key. |
| `404` | Strategy not found for the authenticated user. |
