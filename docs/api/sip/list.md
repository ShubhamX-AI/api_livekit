# List SIP Trunks

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
