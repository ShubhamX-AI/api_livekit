# SIP Trunk Management

This section covers the management of SIP trunks for outbound calling.

## Overview

SIP trunks connect your LiveKit agents to telephony providers (Twilio, Exotel), enabling outbound calls to phone numbers. Each trunk contains authentication credentials and configuration for a specific provider.

## Create Outbound Trunk

Configure a SIP trunk for outbound calls.

- **URL**: `/sip/create-outbound-trunk`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field          | Type   | Required | Description                                       |
| :------------- | :----- | :------- | :------------------------------------------------ |
| `trunk_name`   | string | Yes      | Name of the trunk (1-100 characters).             |
| `trunk_type`   | string | Yes      | Provider type. One of: `twilio`, `exotel`.        |
| `trunk_config` | object | Yes      | The trunk configuration object (see below).       |

### Trunk Configuration

=== "Twilio Configuration"

    Use this when `trunk_type` is set to `"twilio"`.

    | Field      | Type   | Required | Description                                                      |
    | :--------- | :----- | :------- | :--------------------------------------------------------------- |
    | `address`  | string | Yes      | Your Twilio SIP domain (e.g., `example.pstn.twilio.com`).        |
    | `numbers`  | array  | Yes      | List of phone numbers associated with this trunk (E.164 format). |
    | `username` | string | Yes      | Twilio Account SID.                                              |
    | `password` | string | Yes      | Twilio Auth Token.                                               |

=== "Exotel Configuration"

    Use this when `trunk_type` is set to `"exotel"`.

    | Field           | Type   | Required | Description                                           |
    | :-------------- | :----- | :------- | :---------------------------------------------------- |
    | `exotel_number` | string | Yes      | Your Exotel virtual number (caller ID).               |
    | `sip_host`      | string | No       | Optional Exotel SIP proxy host (overrides default).   |
    | `sip_port`      | number | No       | Optional Exotel SIP proxy port (overrides default).   |
    | `sip_domain`    | string | No       | Optional Exotel SIP domain/realm (overrides default). |

### Response Schema

| Field           | Type    | Description                                         |
| :-------------- | :------ | :-------------------------------------------------- |
| `success`       | boolean | Indicates if the operation was successful.          |
| `message`       | string  | Human-readable success message.                     |
| `data`          | object  | Contains the trunk details.                         |
| `data.trunk_id` | string  | Unique identifier for the trunk (format: `ST_...`). |

### HTTP Status Codes

| Code | Description                                                 |
| :--- | :---------------------------------------------------------- |
| 200  | Success - Trunk created successfully.                       |
| 400  | Bad Request - Invalid input data or mismatched configuration. |
| 401  | Unauthorized - Invalid or missing Bearer token.             |
| 500  | Server Error - Internal server error during trunk creation. |

### Example: Twilio Trunk

```bash
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "trunk_name": "Twilio Production",
           "trunk_type": "twilio",
           "trunk_config": {
             "address": "example.pstn.twilio.com",
             "numbers": ["+15550100000"],
             "username": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
             "password": "your_auth_token_here"
           }
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
curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <your_api_key>" \
     -d '{
           "trunk_name": "Exotel India",
           "trunk_type": "exotel",
           "trunk_config": {
             "exotel_number": "+918044319240"
           }
         }'
```

---

## List SIP Trunks

List all active SIP trunks created by the current user.

- **URL**: `/sip/list`
- **Method**: `GET`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Response Schema

| Field                     | Type    | Description                                  |
| :------------------------ | :------ | :------------------------------------------- |
| `success`                 | boolean | Indicates if the operation was successful.    |
| `message`                 | string  | Human-readable success message.              |
| `data`                    | array   | List of trunk objects.                       |
| `data[].trunk_id`         | string  | Unique identifier for the trunk.             |
| `data[].trunk_name`       | string  | Name of the trunk.                           |
| `data[].trunk_type`       | string  | Provider type (`twilio` or `exotel`).       |
| `data[].trunk_created_at` | string  | ISO 8601 timestamp of creation.              |

!!! note "Security Note"

    Trunk configuration details (`trunk_config`) are **not** included in the list response for security reasons.

### HTTP Status Codes

| Code | Description                                     |
| :--- | :---------------------------------------------- |
| 200  | Success - Trunks retrieved successfully.        |
| 401  | Unauthorized - Invalid or missing Bearer token. |
| 500  | Server Error - Internal server error.           |

### Example Request

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/sip/list" \
     -H "Authorization: Bearer <your_api_key>"
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
      "trunk_type": "twilio",
      "trunk_created_at": "2024-01-15T10:00:00.000000"
    },
    {
      "trunk_id": "ST_b2c3d4e5f6a7...",
      "trunk_name": "Exotel India",
      "trunk_type": "exotel",
      "trunk_created_at": "2024-01-15T11:00:00.000000"
    }
  ]
}
```

---

## Provider Setup Guides

### Twilio Setup (LiveKit Managed)

1. **Create a SIP Domain** in Twilio Console.
2. **Configure Authentication** using Credentials list.
3. **Verify Caller IDs** in Twilio.
4. **Use in API**:
   - Set `trunk_type` to `"twilio"`.
   - Provide SIP address, numbers, and credentials in `trunk_config`.

### Exotel Setup (Custom Bridge)

1. **Get an Exotel Virtual Number** from your Exotel dashboard.
2. **Use in API**:
   - Set `trunk_type` to `"exotel"`.
   - Provide your virtual number in `trunk_config.exotel_number`.
   - Optional: Provide `sip_host`, `sip_port`, or `sip_domain` if using a private configuration.

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
