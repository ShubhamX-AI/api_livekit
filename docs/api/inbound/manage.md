# Manage Inbound Numbers

Create and maintain inbound number mappings for assistants.

- **Base URL**: `/inbound`
- **Auth**: `Authorization: Bearer <your_api_key>`
- **Supported service**: `exotel`

## Data Model Notes

- `phone_number` stores the original value you submitted.
- `phone_number_normalized` stores the normalized value used for routing and uniqueness checks.
- `assistant_id` is nullable after detach/update.
- `inbound_context_strategy_id` is optional and nullable.
- Active uniqueness is enforced on the normalized phone number across the full system.
- A mapping can route calls without a strategy, but cannot route calls without a valid attached assistant.

## Assign Inbound Number

- **URL**: `/inbound/assign`
- **Method**: `POST`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Active assistant owned by the authenticated user. |
| `inbound_context_strategy_id` | string | No | Optional strategy ID for caller-context lookup before prompt rendering. |
| `service` | string | Yes | Must be `exotel`. |
| `inbound_config` | object | Yes | Provider-specific inbound config. |
| `inbound_config.type` | string | Yes | Must match `service`. If omitted, the API injects it from `service`. |
| `inbound_config.phone_number` | string | Yes | Exotel inbound number to store and normalize. |

### Example Request (Without Strategy)

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound/assign" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "service": "exotel",
           "inbound_config": {
             "phone_number": "+918044319240"
           }
         }'
```

### Example Request (With Strategy)

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/inbound/assign" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
           "inbound_context_strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
           "service": "exotel",
           "inbound_config": {
             "phone_number": "+918044319240"
           }
         }'
```

### Success Response

```json
{
  "success": true,
  "message": "Inbound number assigned successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "phone_number": "+918044319240",
    "phone_number_normalized": "918044319240",
    "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
    "inbound_context_strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
    "inbound_context_strategy_name": "CRM lookup",
    "service": "exotel",
    "inbound_config": {
      "type": "exotel",
      "phone_number": "+918044319240"
    }
  }
}
```

### Common Errors

| Code | Reason |
| :--- | :--- |
| `400` | Unsupported service or invalid inbound phone number. |
| `404` | Assistant not found for the authenticated user. |
| `404` | Inbound context strategy not found (if provided). |
| `409` | Normalized inbound number is already assigned to an active mapping. |

## Update Mapping Fields

- **URL**: `/inbound/update/{inbound_id}`
- **Method**: `PATCH`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string or null | No | Replace assistant, or set `null` to detach assistant. |
| `inbound_context_strategy_id` | string or null | No | Replace strategy, or set `null` to detach strategy. |

You can update one field without changing the other.

### Example Request: Update Assistant Only

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound/update/9c2ad915-7d8a-4949-b8df-5fd0da91b4e6" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "de305d54-75b4-431b-adb2-eb6b9e546014"
         }'
```

### Example Request: Update Strategy Only

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound/update/9c2ad915-7d8a-4949-b8df-5fd0da91b4e6" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "inbound_context_strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de"
         }'
```

### Example Request: Clear Strategy

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound/update/9c2ad915-7d8a-4949-b8df-5fd0da91b4e6" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "inbound_context_strategy_id": null
         }'
```

### Success Response

```json
{
  "success": true,
  "message": "Inbound number mapping updated successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "assistant_id": "de305d54-75b4-431b-adb2-eb6b9e546014",
    "inbound_context_strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de"
  }
}
```

## Detach Inbound Number

- **URL**: `/inbound/detach/{inbound_id}`
- **Method**: `POST`

This clears `assistant_id` but keeps the inbound number mapping active and visible in `/inbound/list`.

It also clears `inbound_context_strategy_id`.

### Success Response

```json
{
  "success": true,
  "message": "Inbound number detached successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "assistant_id": null,
    "inbound_context_strategy_id": null
  }
}
```

## Delete Inbound Number

- **URL**: `/inbound/delete/{inbound_id}`
- **Method**: `DELETE`

This marks the mapping inactive, clears `assistant_id`, and releases the normalized number for reuse.

It also clears `inbound_context_strategy_id`.

### Success Response

```json
{
  "success": true,
  "message": "Inbound number deleted successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6"
  }
}
```

## List Inbound Numbers

- **URL**: `/inbound/list`
- **Method**: `GET`

### Response Fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `data[].inbound_id` | string | Unique mapping ID. |
| `data[].phone_number` | string | Original inbound number value. |
| `data[].phone_number_normalized` | string | Normalized number used by the router. |
| `data[].inbound_config` | object | Stored provider config. |
| `data[].assistant_id` | string or null | Attached assistant ID. |
| `data[].assistant_name` | string or null | Assistant name resolved for the current user. |
| `data[].inbound_context_strategy_id` | string or null | Attached strategy ID. |
| `data[].inbound_context_strategy_name` | string or null | Attached strategy name for convenience. |
| `data[].service` | string | Provider name stored with the mapping. |
| `data[].created_at` | string | Mapping creation timestamp. |
| `data[].updated_at` | string | Last update timestamp. |

### Example Response

```json
{
  "success": true,
  "message": "Inbound numbers retrieved successfully",
  "data": [
    {
      "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
      "phone_number": "+918044319240",
      "phone_number_normalized": "918044319240",
      "inbound_config": {
        "type": "exotel",
        "phone_number": "+918044319240"
      },
      "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
      "assistant_name": "Support Assistant",
      "inbound_context_strategy_id": "f0f6d398-f9d9-4a7b-bc8e-4f24f57ec2de",
      "inbound_context_strategy_name": "CRM lookup",
      "service": "exotel",
      "created_at": "2026-03-18T11:30:00Z",
      "updated_at": "2026-03-18T11:30:00Z"
    }
  ]
}
```

## Operational Notes

- If `assistant_id` is null, inbound calls to that number do not route to an agent.
- If `inbound_context_strategy_id` is null, inbound calls still route and run without caller-context lookup.
- If a referenced strategy is deleted, active mappings are automatically detached from that strategy and continue routing without context lookup.
