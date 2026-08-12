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
- No field may be sent as `null`. Omit a field to leave it unchanged.

## Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `strategy_name` | string | No | New display name. |
| `strategy_type` | string | No | Must be `webhook` when sent. |
| `strategy_config` | object | No | Partial config update for the strategy. |
| `strategy_config.url` | string | No | New webhook URL. Must be `http`/`https` and must not resolve to a private, loopback, link-local, or reserved address. See [URL Requirements](index.md#url-requirements). |
| `strategy_config.headers` | object | No | Merged into the stored headers, key by key. A header sent with value `null` is deleted. |
| `strategy_config.timeout_seconds` | number | No | New timeout value (`0.5` to `10.0`, default `10.0`). |

Header keys are not restricted. Use any keys required by your webhook endpoint.

## Important Merge Behavior

Top-level `strategy_config` keys replace, but `headers` merges.

- If you update only `timeout_seconds`, existing `url` and `headers` remain.
- If you send `headers`, each key you send is added or overwritten; every other stored header is left alone.
- To delete one header, send it with a `null` value.

Starting from stored headers `{"Authorization": "Bearer old", "X-Tenant-Id": "acme"}`:

| PATCH `headers` | Resulting stored headers |
| :--- | :--- |
| `{"X-Region": "in"}` | `Authorization: Bearer old`, `X-Tenant-Id: acme`, `X-Region: in` |
| `{"Authorization": "Bearer new"}` | `Authorization: Bearer new`, `X-Tenant-Id: acme` |
| `{"X-Tenant-Id": null}` | `Authorization: Bearer old` |
| omitted entirely | unchanged |

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

## Example: Rotate the Token, Keep Other Headers

Every other stored header survives — you do not need to resend them.

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

## Example: Add One Header

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/update/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_type": "webhook",
           "strategy_config": {
             "headers": {
               "X-Region": "in"
             }
           }
         }'
```

## Example: Delete One Header

Send the header with a `null` value.

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/update/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_type": "webhook",
           "strategy_config": {
             "headers": {
               "X-Tenant-Id": null
             }
           }
         }'
```

## Example: Change the Webhook URL

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/update/f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_type": "webhook",
           "strategy_config": {
             "url": "https://crm.example.com/caller-context-v2"
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

| Code | Reason | Message |
| :--- | :--- | :--- |
| `400` | No fields sent | `No fields provided for update` |
| `400` | `strategy_type` sent without `strategy_config` (or the reverse) | ``Provide both `strategy_type` and `strategy_config` together, or neither.`` |
| `400` | A field sent as `null` | ``` `strategy_config` cannot be null; omit it to leave it unchanged. ``` |
| `400` | A masked value echoed back from `GET /details` | ``` 'Authorization' is masked (as returned by GET /tool/details). Send the real value, or omit the field to keep the stored one. ``` |
| `400` | URL scheme not `http`/`https` | `url must use http or https` |
| `400` | URL points at a non-public address | `url host '169.254.169.254' resolves to a non-public address` |
| `400` | URL host is internal | `url host 'localhost' is not allowed` |
| `400` | `timeout_seconds` outside `0.5`–`10.0` | Pydantic range error on `strategy_config.timeout_seconds` |
| `401` | Invalid or missing API key. | |
| `404` | Strategy not found for the authenticated user. | |

!!! danger "Do not echo back masked values"

    `GET /details` and `GET /list` return secret-looking header values as `****`. Sending that `****` back on update is rejected with `400` — by design. Without it, a fetch-edit-save round trip would overwrite your real token with the literal string `****` and every subsequent lookup would fail with `401` from your own endpoint.

    Because headers now merge, the safe pattern is simply: send only the headers you are actually changing, and never resend a header you did not edit.
