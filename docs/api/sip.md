# SIP Trunk Management

This section covers the management of SIP trunks for outbound calling.

## Overview

SIP trunks connect your LiveKit agents to telephony providers (Twilio, Exotel), enabling outbound calls to phone numbers. Each trunk contains authentication credentials and configuration for a specific provider.

## Create Outbound Trunk

Configure a SIP trunk for outbound calls.

- **URL**: `/sip/create-outbound-trunk`
- **Method**: `POST`
- **Headers**: `x-api-key: <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `trunk_name` | string | Yes | Name of the trunk (1-100 characters). |
| `trunk_address` | string | Yes | SIP address/domain of the provider. |
| `trunk_numbers` | array | Yes | List of phone numbers associated with this trunk (E.164 format). |
| `trunk_auth_username` | string | Yes | SIP authentication username. |
| `trunk_auth_password` | string | Yes | SIP authentication password. |
| `trunk_type` | string | Yes | Provider type. One of: `twilio`, `exotel`. |

### Trunk Type Details

=== "Twilio"

    | Field | Example Value | Description |
    | :--- | :--- | :--- |
    | `trunk_address` | `example.pstn.twilio.com` | Your Twilio SIP domain |
    | `trunk_auth_username` | `ACxxxxx...` | Twilio Account SID |
    | `trunk_auth_password` | `your_auth_token` | Twilio Auth Token |
    | `trunk_numbers` | `["+15550100000"]` | Verified caller IDs |

=== "Exotel"

    | Field | Example Value | Description |
    | :--- | :--- | :--- |
    | `trunk_address` | `sip.exotel.com` | Exotel SIP endpoint |
    | `trunk_auth_username` | `your_exotel_sid` | Exotel SID |
    | `trunk_auth_password` | `your_token` | Exotel Token |
    | `trunk_numbers` | `["+911234567890"]` | Exotel phone numbers |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates if the operation was successful. |
| `message` | string | Human-readable success message. |
| `data` | object | Contains the trunk details. |
| `data.trunk_id` | string | Unique identifier for the trunk (format: `ST_...`). |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - Trunk created successfully. |
| 400 | Bad Request - Invalid input data. |
| 401 | Unauthorized - Invalid or missing API key. |
| 500 | Server Error - Internal server error during trunk creation. |

### Example: Twilio Trunk

```bash
curl -X POST "http://localhost:8000/sip/create-outbound-trunk" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "trunk_name": "Twilio Production",
           "trunk_address": "example.pstn.twilio.com",
           "trunk_numbers": ["+15550100000", "+15550100001"],
           "trunk_auth_username": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
           "trunk_auth_password": "your_auth_token_here",
           "trunk_type": "twilio"
         }'
```

**Response:**

```json
{
  "success": true,
  "message": "Outbound trunk created successfully, Store the trunk id securely.",
  "data": {
    "trunk_id": "ST_a1b2c3d4e5f6..."
  }
}
```

### Example: Exotel Trunk

```bash
curl -X POST "http://localhost:8000/sip/create-outbound-trunk" \
     -H "Content-Type: application/json" \
     -H "x-api-key: <your_api_key>" \
     -d '{
           "trunk_name": "Exotel India",
           "trunk_address": "sip.exotel.com",
           "trunk_numbers": ["+911234567890"],
           "trunk_auth_username": "your_exotel_sid",
           "trunk_auth_password": "your_exotel_token",
           "trunk_type": "exotel"
         }'
```

---

## List SIP Trunks

List all active SIP trunks created by the current user.

- **URL**: `/sip/list`
- **Method**: `GET`
- **Headers**: `x-api-key: <your_api_key>`

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates if the operation was successful. |
| `message` | string | Human-readable success message. |
| `data` | array | List of trunk objects. |
| `data[].trunk_id` | string | Unique identifier for the trunk. |
| `data[].trunk_name` | string | Name of the trunk. |
| `data[].trunk_address` | string | SIP address/domain. |
| `data[].trunk_numbers` | array | Associated phone numbers. |
| `data[].trunk_type` | string | Provider type (`twilio` or `exotel`). |
| `data[].trunk_created_at` | string | ISO 8601 timestamp of creation. |

!!! note "Security Note"

    Authentication credentials (`trunk_auth_username` and `trunk_auth_password`) are **not** included in the list response for security reasons. Use the individual trunk details endpoint if needed.

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - Trunks retrieved successfully. |
| 401 | Unauthorized - Invalid or missing API key. |
| 500 | Server Error - Internal server error. |

### Example Request

```bash
curl -X GET "http://localhost:8000/sip/list" \
     -H "x-api-key: <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "SIP trunks retrieved successfully",
  "data": [
    {
      "trunk_id": "ST_a1b2c3d4e5f6...",
      "trunk_name": "Twilio Production",
      "trunk_address": "example.pstn.twilio.com",
      "trunk_numbers": ["+15550100000", "+15550100001"],
      "trunk_type": "twilio",
      "trunk_created_at": "2024-01-15T10:00:00.000000"
    },
    {
      "trunk_id": "ST_b2c3d4e5f6a7...",
      "trunk_name": "Exotel India",
      "trunk_address": "sip.exotel.com",
      "trunk_numbers": ["+911234567890"],
      "trunk_type": "exotel",
      "trunk_created_at": "2024-01-15T11:00:00.000000"
    }
  ]
}
```

---

## Provider Setup Guides

### Twilio Setup

1. **Create a SIP Domain** in Twilio Console:
   - Go to Elastic SIP Trunking → SIP Trunks → Create new SIP Trunk
   - Note down the Termination SIP URI

2. **Configure Authentication**:
   - Set Credential List for authentication
   - Use your Account SID as username
   - Use Auth Token or API Key Secret as password

3. **Verify Caller IDs**:
   - Add numbers to the trunk in E.164 format (+1555...)
   - Verify each number in Twilio

4. **Use in API**:
   - Set `trunk_address` to your Termination SIP URI
   - Set `trunk_type` to `"twilio"`

### Exotel Setup

1. **Get Credentials** from Exotel Dashboard:
   - SID (Account identifier)
   - Token (Authentication token)

2. **Configure Phone Numbers**:
   - List all numbers to use for outbound calling
   - Ensure numbers are activated for outbound

3. **Use in API**:
   - Set `trunk_address` to `"sip.exotel.com"`
   - Set `trunk_type` to `"exotel"`

---

## Next Steps

After creating a SIP trunk:

1. Note the `trunk_id` from the response
2. [Create an Assistant](assistant.md) (if you haven't already)
3. [Trigger an outbound call](calls.md) using the trunk and assistant

---

## Troubleshooting

### Common Issues

!!! failure "Authentication Failed"

    **Error**: Call fails with authentication error

    **Solution**: 
    - Verify Account SID and Auth Token are correct
    - Check that credentials are URL-encoded if they contain special characters
    - Ensure the SIP domain allows your IP address

!!! failure "Invalid Number"

    **Error**: Provider rejects the destination number

    **Solution**:
    - Ensure number is in E.164 format (+ followed by country code)
    - Check that the trunk supports the destination country
    - Verify number is not on a do-not-call list

!!! failure "Trunk Not Found"

    **Error**: `404` when using trunk ID

    **Solution**:
    - Verify you're using the full trunk ID (starts with `ST_`)
    - Ensure the trunk belongs to your user account
    - Check that the trunk hasn't been deleted
