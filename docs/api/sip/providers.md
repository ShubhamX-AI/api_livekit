# Provider Setup Guides

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
2. [Create an Assistant](../assistant/create.md) (if you haven't already)
3. [Trigger an outbound call](../calls/trigger.md) using the trunk and assistant

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
