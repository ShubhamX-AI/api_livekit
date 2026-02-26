# Create Outbound Trunk

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
