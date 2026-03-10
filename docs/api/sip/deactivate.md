# Deactivate SIP Trunk

Deactivates an outbound SIP trunk. The trunk is soft-deleted — it is marked as inactive in the database but not permanently removed. A deactivated trunk cannot be used to trigger outbound calls.

- **URL**: `/sip/deactivate/{trunk_id}`
- **Method**: `DELETE`
- **Headers**: `Authorization: Bearer <your_api_key>`

### Path Parameters

| Parameter  | Type   | Description                             |
| :--------- | :----- | :-------------------------------------- |
| `trunk_id` | string | The unique identifier of the SIP trunk. |

### Response Schema

| Field       | Type    | Description                               |
| :---------- | :------ | :---------------------------------------- |
| `success`   | boolean | Indicates if the operation was successful. |
| `message`   | string  | Human-readable success message.           |
| `data`      | object  | Contains the deactivated trunk's details. |
| `data.trunk_id` | string | The trunk ID that was deactivated.    |

### HTTP Status Codes

| Code | Description                                                      |
| :--- | :--------------------------------------------------------------- |
| 200  | Success - Trunk deactivated successfully.                        |
| 400  | Bad Request - Trunk is already deactivated.                      |
| 401  | Unauthorized - Invalid or missing Bearer token.                  |
| 404  | Not Found - Trunk does not exist or belongs to another user.     |
| 500  | Server Error - Internal server error.                            |

### Example Request

```bash
curl -X DELETE "https://api-livekit-vyom.indusnettechnologies.com/sip/deactivate/ST_a1b2c3d4e5f6" \
     -H "Authorization: Bearer <your_api_key>"
```

**Response:**

```json
{
  "success": true,
  "message": "Trunk deactivated successfully",
  "data": {
    "trunk_id": "ST_a1b2c3d4e5f6"
  }
}
```

**Already deactivated (400):**

```json
{
  "detail": "Trunk is already deactivated"
}
```

**Trunk not found (404):**

```json
{
  "detail": "Trunk not found"
}
```

!!! warning "Effect on Outbound Calls"

    Once a trunk is deactivated, any attempt to trigger an outbound call using its `trunk_id` will return a **404 Trunk not found** error. Deactivate trunks only when they are no longer needed.

!!! note "Not a Hard Delete"

    Deactivation sets `trunk_is_active` to `false` in the database. The trunk record is preserved for audit purposes. Deactivated trunks do **not** appear in the [List Trunks](list.md) response.
