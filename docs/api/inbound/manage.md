# Manage Inbound Numbers

Create and maintain inbound number mappings for assistants.

- **Base URL**: `/inbound`
- **Auth**: `Authorization: Bearer <your_api_key>`
- **Supported service**: `exotel`

## Data Model Notes

- `phone_number` stores the original value you submitted.
- `phone_number_normalized` stores the normalized value used for routing and uniqueness checks.
- `assistant_id` is nullable after detach.
- Active uniqueness is enforced on the normalized phone number across the full system.

## Assign Inbound Number

- **URL**: `/inbound/assign`
- **Method**: `POST`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Active assistant owned by the authenticated user. |
| `service` | string | Yes | Must be `exotel`. |
| `inbound_config` | object | Yes | Provider-specific inbound config. |
| `inbound_config.type` | string | Yes | Must match `service`. If omitted, the API injects it from `service`. |
| `inbound_config.phone_number` | string | Yes | Exotel inbound number to store and normalize. |

### Example Request

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
| `409` | Normalized inbound number is already assigned to an active mapping. |

## Update Attached Assistant

- **URL**: `/inbound/update/{inbound_id}`
- **Method**: `PATCH`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Replacement assistant owned by the authenticated user. |

### Example Request

```bash
curl -X PATCH "https://api-livekit-vyom.indusnettechnologies.com/inbound/update/9c2ad915-7d8a-4949-b8df-5fd0da91b4e6" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "assistant_id": "de305d54-75b4-431b-adb2-eb6b9e546014"
         }'
```

### Success Response

```json
{
  "success": true,
  "message": "Inbound number mapping updated successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "assistant_id": "de305d54-75b4-431b-adb2-eb6b9e546014"
  }
}
```

## Detach Inbound Number

- **URL**: `/inbound/detach/{inbound_id}`
- **Method**: `POST`

This clears `assistant_id` but keeps the inbound number mapping active and visible in `/inbound/list`.

### Success Response

```json
{
  "success": true,
  "message": "Inbound number detached successfully",
  "data": {
    "inbound_id": "9c2ad915-7d8a-4949-b8df-5fd0da91b4e6",
    "assistant_id": null
  }
}
```

## Delete Inbound Number

- **URL**: `/inbound/delete/{inbound_id}`
- **Method**: `DELETE`

This marks the mapping inactive, clears `assistant_id`, and releases the normalized number for reuse.

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
      "service": "exotel",
      "created_at": "2026-03-18T11:30:00Z",
      "updated_at": "2026-03-18T11:30:00Z"
    }
  ]
}
```
