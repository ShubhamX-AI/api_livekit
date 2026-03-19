# List Inbound Context Strategies

List active strategies owned by the authenticated user.

- **URL**: `/inbound_context_strategy/list`
- **Method**: `GET`
- **Auth**: `Authorization: Bearer <your_api_key>`

## What You Get

Returns all active strategies in descending creation order.

## Response Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `data[].strategy_id` | string | Unique strategy ID. |
| `data[].strategy_name` | string | Strategy display name. |
| `data[].strategy_type` | string | Strategy type (`webhook`). |
| `data[].strategy_config` | object | Strategy configuration with sensitive headers masked. |
| `data[].strategy_created_at` | string | Creation timestamp (UTC). |
| `data[].strategy_updated_at` | string | Last update timestamp (UTC). |

## Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/list" \
     -H "Authorization: Bearer <your_api_key>"
```

## Example Response

```json
{
  "success": true,
  "message": "Inbound context strategies retrieved successfully",
  "data": [
    {
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
      "strategy_created_at": "2026-03-19T09:10:00Z",
      "strategy_updated_at": "2026-03-19T09:10:00Z"
    }
  ]
}
```

## Notes

- Only active strategies are returned.
- Header masking is for response safety only; stored values are not overwritten by masking.
