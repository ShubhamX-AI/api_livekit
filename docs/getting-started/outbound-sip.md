# Outbound SIP Call

Queue a phone call via Twilio or Exotel.

Prerequisite: complete [Step 1–3](index.md) to have an `assistant_id`.

## A1 — Create a SIP Trunk

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "trunk_name": "My Twilio Trunk",
        "trunk_address": "your-twilio-sip-domain.sip.twilio.com",
        "trunk_numbers": ["+15550100000"],
        "trunk_auth_username": "your_twilio_username",
        "trunk_auth_password": "your_twilio_password",
        "trunk_type": "twilio"
      }'
    ```

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/sip/create-outbound-trunk" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "trunk_name": "My Exotel Trunk",
        "trunk_type": "exotel",
        "trunk_config": {
          "exotel_number": "+918044319240"
        }
      }'
    ```

Save the `trunk_id` (format: `ST_...`) from the response.

## A2 — Trigger the Call

=== "Twilio"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "assistant_id": "ASSISTANT_ID",
        "trunk_id": "TRUNK_ID",
        "to_number": "+15550100000",
        "call_service": "twilio"
      }'
    ```

    A `202 Accepted` response means the request was queued successfully. Save the returned `queue_id`.

=== "Exotel"

    ```bash
    curl -X POST "https://api-livekit-vyom.indusnettechnologies.com/call/outbound" \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "assistant_id": "ASSISTANT_ID",
        "trunk_id": "TRUNK_ID",
        "to_number": "+918044319240",
        "call_service": "exotel"
      }'
    ```

    A `202 Accepted` response means the request was queued successfully. Save the returned `queue_id`.

Example response:

```json
{
  "success": true,
  "message": "Outbound call queued successfully",
  "data": {
    "queue_id": "QUEUE_ID",
    "status": "queued"
  }
}
```

## A3 — Check Queue Status

```bash
curl -X GET "https://api-livekit-vyom.indusnettechnologies.com/call/queue/QUEUE_ID" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Use this endpoint to see whether the request is still `pending`, currently `dispatching`, already `dispatched`, or permanently `failed`.

## A4 — Track the Final Call Outcome

Once the queue item becomes `dispatched`, track the live call outcome through:

- the assistant end-call webhook (`assistant_end_call_url`)
- `GET /assistant/call-logs/{assistant_id}`

The final outcome (`answered`, `completed`, `busy`, `no_answer`, and so on) is not stored on the queue item itself.
