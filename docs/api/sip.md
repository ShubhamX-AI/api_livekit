# SIP Trunk Management

This section covers the management of SIP trunks for outbound calling.

## Create Outbound Trunk

Configure a SIP trunk for outbound calls.

- **URL**: `/sip/create-outbound-trunk`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `trunk_name` | string | Yes | Name of the trunk. |
| `trunk_address` | string | Yes | SIP address/domain of the provider. |
| `trunk_numbers` | array | Yes | List of phone numbers associated with this trunk. |
| `trunk_auth_username` | string | Yes | SIP authentication username. |
| `trunk_auth_password` | string | Yes | SIP authentication password. |
| `trunk_type` | string | Yes | `twilio` (currently the only supported type). |

### Example

```bash
curl -X POST "http://localhost:8000/sip/create-outbound-trunk" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "trunk_name": "Twilio Trunk",
           "trunk_address": "example.pstn.twilio.com",
           "trunk_numbers": ["+15550100000"],
           "trunk_auth_username": "twilio_user",
           "trunk_auth_password": "twilio_password",
           "trunk_type": "twilio"
         }'
```

```json
{
  "success": true,
  "message": "Outbound trunk created successfully, Store the trunk id securely.",
  "data": {
    "trunk_id": "ST_..."
  }
}
```

## List SIP Trunks

List all active SIP trunks created by the current user.

- **URL**: `/sip/list`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Example

```bash
curl -X GET "http://localhost:8000/sip/list" \
     -H "x-api-key: <your_api_key>"
```
