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
| `strategy_config.url` | string | Yes | Webhook URL that returns caller context. Must be `http`/`https` and must not resolve to a private, loopback, link-local, or reserved address. |
| `strategy_config.headers` | object | No | Optional request headers for webhook auth/customization. |
| `strategy_config.timeout_seconds` | number | No | Timeout in seconds. Defaults to `2.0`. Allowed range: `0.5` to `10.0`. |

`strategy_config.headers` can contain any header keys your webhook expects (for example `Authorization`, `X-API-Key`, `X-Tenant-Id`).

### URL Rules

| Rule | Accepted | Rejected |
| :--- | :--- | :--- |
| Scheme is `http` or `https` | `https://crm.example.com/ctx` | `ftp://crm.example.com/ctx` |
| Host is not a private/loopback/link-local/reserved IP | `https://203.0.113.10/ctx` | `https://127.0.0.1/ctx`, `https://10.0.0.5/ctx`, `https://169.254.169.254/…` |
| Host is not an internal name | `https://internal.example.com/ctx` | `https://localhost/ctx`, `https://metadata.google.internal/ctx` |

Full detail in [URL Requirements](index.md#url-requirements). Plain `http` is allowed, but the request carries the caller's phone number and your `Authorization` header in cleartext — prefer `https`.

The timeout blocks the start of the call, so keep it low. A `10.0` timeout against a slow endpoint means up to 10 seconds of silence for the caller. See [Runtime Behavior](index.md#runtime-behavior).

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

## Example: Rejected URL

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound_context_strategy/create" \
     -H "Authorization: Bearer <your_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
           "strategy_name": "bad",
           "strategy_type": "webhook",
           "strategy_config": { "url": "https://169.254.169.254/latest/meta-data/" }
         }'
```

```json
{
  "detail": [
    {
      "loc": ["body", "strategy_config", "url"],
      "msg": "Value error, url host '169.254.169.254' resolves to a non-public address"
    }
  ]
}
```

## If You Do Not Attach It Anywhere

Nothing changes at runtime until the strategy is attached to an inbound mapping. Creating a strategy has no effect on any call by itself, and inbound numbers without a strategy keep working exactly as before — see [Without a Strategy the Call Is Unaffected](index.md#without-a-strategy-the-call-is-unaffected).

## Common Errors

| Code | Reason | Message |
| :--- | :--- | :--- |
| `400` | URL scheme not `http`/`https` | `url must use http or https` |
| `400` | URL points at a non-public address | `url host '10.0.0.5' resolves to a non-public address` |
| `400` | URL host is internal | `url host 'localhost' is not allowed` |
| `400` | A header value is the literal mask `****` | ``` 'Authorization' is masked (as returned by GET /tool/details). Send the real value, or omit the field to keep the stored one. ``` |
| `400` | `timeout_seconds` outside `0.5`–`10.0` | Pydantic range error on `strategy_config.timeout_seconds` |
| `400` | Other validation or create failure (for example invalid config shape). | |
| `401` | Invalid or missing API key. | |
