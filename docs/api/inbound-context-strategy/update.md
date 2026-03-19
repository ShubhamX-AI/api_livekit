# Update Inbound Context Strategy

Update strategy metadata and/or strategy configuration.

- **URL**: `/inbound_context_strategy/update/{strategy_id}`
- **Method**: `PATCH`
- **Auth**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

## Update Rules

- Send at least one field.
- If you send `strategy_type`, you must also send `strategy_config`.
- If you send `strategy_config`, you must also send `strategy_type`.
- Strategy type currently supports only `webhook`.

## Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `strategy_name` | string | No | New display name. |
| `strategy_type` | string | No | Must be `webhook` when sent. |
| `strategy_config` | object | No | Partial config update for the strategy. |
| `strategy_config.url` | string | No | New webhook URL. |
| `strategy_config.headers` | object | No | Replaces stored headers when sent. |
| `strategy_config.timeout_seconds` | number | No | New timeout value (`0.5` to `10.0`). |

Header keys are not restricted. Use any keys required by your webhook endpoint.

## Important Merge Behavior

The update merges top-level `strategy_config` keys with existing config.

- If you update only `timeout_seconds`, existing `url` and `headers` remain.
- If you send `headers`, the headers object is replaced with the object you provide.

## Example: Update Timeout Only

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/update/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_type": "webhook",
           "strategy_config": {
             "timeout_seconds": 3.5
           }
         }'
```

## Example: Replace Headers

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/update/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_type": "webhook",
           "strategy_config": {
             "headers": {
               "Authorization": "Bearer rotated-token"
             }
           }
         }'
```

## Success Response

```json
{
  "success": true,
  "message": "Inbound context strategy updated successfully",
  "data": {
    "strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de"
  }
}
```

## Common Errors

| Code | Reason |
| :--- | :--- |
| `400` | Missing fields, invalid update shape, or validation failure. |
| `401` | Invalid or missing API key. |
| `404` | Strategy not found for the authenticated user. |
