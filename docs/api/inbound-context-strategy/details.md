# Get Inbound Context Strategy Details

Fetch one active strategy by ID.

- **URL**: `/inbound_context_strategy/details/{strategy_id}`
- **Method**: `GET`
- **Auth**: `Authorization: Bearer <your_api_key>`

## What This Is For

Use this when you want to inspect one strategy before attaching it to inbound mappings or before updating it.

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/details/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>"
```

## Example Response

```json
{
  "success": true,
  "message": "Inbound context strategy retrieved successfully",
  "data": {
    "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
    "strategy_name": "CRM lookup",
    "strategy_type": "webhook",
    "strategy_config": {
      "type": "webhook",
      "url": "https://example.com/caller-context",
      "headers": {
        "Authorization": "****"
      },
      "timeout_seconds": 2.0
    },
    "strategy_created_by_email": "admin@example.com",
    "strategy_updated_by_email": "admin@example.com",
    "strategy_created_at": "2026-03-19T09:10:00Z",
    "strategy_updated_at": "2026-03-19T09:10:00Z",
    "strategy_is_active": true
  }
}
```

## Notes

- Sensitive header values are masked in response payloads.
- Inactive or foreign-user strategies return `404`.
