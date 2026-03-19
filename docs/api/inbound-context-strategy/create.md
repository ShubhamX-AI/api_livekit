# Create Inbound Context Strategy

Create a reusable inbound caller-context strategy.

- **URL**: `/inbound_context_strategy/create`
- **Method**: `POST`
- **Auth**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

## What This Does

Creates a strategy that can later be attached to one or more inbound number mappings.

## Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `strategy_name` | string | Yes | Human-readable name for this strategy. |
| `strategy_type` | string | Yes | Must be `webhook`. |
| `strategy_config` | object | Yes | Type-specific config object. |
| `strategy_config.url` | string | Yes | Webhook URL that returns caller context. |
| `strategy_config.headers` | object | No | Optional request headers for webhook auth/customization. |
| `strategy_config.timeout_seconds` | number | No | Timeout in seconds. Defaults to `2.0`. Allowed range: `0.5` to `10.0`. |

`strategy_config.headers` can contain any header keys your webhook expects (for example `Authorization`, `X-API-Key`, `X-Tenant-Id`).

## Example Request

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/create" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_name": "CRM lookup",
           "strategy_type": "webhook",
           "strategy_config": {
             "url": "https://example.com/caller-context",
             "headers": {
               "Authorization": "Bearer crm-token"
             },
             "timeout_seconds": 2.0
           }
         }'
```

## Success Response

```json
{
  "success": true,
  "message": "Inbound context strategy created successfully",
  "data": {
    "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
    "strategy_name": "CRM lookup",
    "strategy_type": "webhook"
  }
}
```

## If You Do Not Attach It Anywhere

Nothing changes at runtime until the strategy is attached to an inbound mapping.

## Common Errors

| Code | Reason |
| :--- | :--- |
| `400` | Validation error or create failure (for example invalid config shape). |
| `401` | Invalid or missing API key. |
