# Join a Meeting

Put an assistant into a video meeting. The assistant joins as an ordinary participant, hears
everyone in the meeting, and speaks back into it.

Google Meet is the only supported platform today. The API is shaped so that adding Zoom or Teams
later is a new value of `platform` and nothing else.

- **URL**: `/meeting_call/join`
- **Method**: `POST`
- **Headers**: `Authorization: Bearer <your_api_key>`
- **Content-Type**: `application/json`

### Request Body

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `assistant_id` | string | Yes | Assistant ID to run in the meeting. |
| `meeting_url` | string | Yes | Link to the meeting. For Google Meet this must look like `https://meet.google.com/abc-defg-hij`. |
| `platform` | string | No | Default `google_meet`. The meeting platform the URL belongs to. |
| `bot_display_name` | string | No | Name shown in the meeting's participant list. Defaults to the assistant's name. |
| `metadata` | object | No | Optional key-value data injected into assistant placeholders. |

### Response Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `success` | boolean | Indicates whether the meeting call started. |
| `message` | string | Human-readable status message. |
| `data.room_name` | string | Unique LiveKit room created for this meeting call. |
| `data.platform` | string | The meeting platform that was joined. |
| `data.meeting_url` | string | The meeting the connector was sent to. |
| `data.connector_container_id` | string | Id of the container running the connector, for operational debugging. |
| `data.agent_dispatch` | object | The LiveKit agent dispatch that was created. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - The connector was launched and the assistant dispatched. |
| 400 | Bad Request - `meeting_url` is not a valid link for `platform`. |
| 422 | Validation Error - Invalid request body. |
| 401 | Unauthorized - Invalid or missing Bearer token. |
| 404 | Not Found - Assistant not found for the authenticated user. |
| 503 | Unavailable - `MAX_CONCURRENT_MEETING_CALLS` reached, or meeting calls are not configured on this deployment. |
| 500 | Server Error - Internal error while starting the meeting call. |

### How it works

A meeting call is a web call whose participant happens to be a browser sitting in a meeting. The
LiveKit room, the agent dispatch, the `CallRecord`, the usage record and the end-of-call webhook
are all the same as a web call. The difference is who joins the room.

1. The API creates a LiveKit room and dispatches the assistant into it, exactly as for a web call.
2. The API launches a **connector** container, telling it the meeting URL and the room name.
3. The connector opens a browser, joins the meeting, and publishes the meeting's audio into the
   LiveKit room as a single participant named `google-meet`.
4. The assistant sets the participant attribute `lk.publish_on_behalf` on itself to the room name.
   The connector subscribes to whichever participant carries that attribute and plays its audio
   into the meeting. This is how the connector finds the assistant without knowing its identity,
   which LiveKit mints inside the job token and nobody can predict beforehand.

### Everyone in the meeting is heard

The connector publishes **one** audio track carrying Google Meet's own mix of every person in the
call, not one track per speaker.

This is deliberate and it is what makes a meeting with several people work. A LiveKit
`AgentSession` listens to one *linked participant* — by default the first to join. With one track
per speaker, an assistant would hear whoever it linked to and be deaf to everybody else, while
appearing to work normally.

The trade-off is that the transcript does not attribute each sentence to a speaker. The roster of
who is in the meeting is still tracked, so nothing about *who is present* is lost — only the
mapping from a sentence back to a person.

### Call records and status

The connector reports its progress to the API, which moves the `CallRecord` along:

| Connector reports | `call_status` |
| :--- | :--- |
| `waiting` | stays `initiated` — someone in the meeting has to admit the bot |
| `joined` | `answered`, with `answered_at` set |
| `failed` | `failed`, with the reason in `call_status_reason`, then the call is ended |
| `ended` | `completed`, firing the end-of-call webhook and finalising usage |

`CallRecord.call_type` is `"meeting"` and `call_service` is the platform (`"google_meet"`).

### Capacity

Meeting calls have their own concurrency cap, `MAX_CONCURRENT_MEETING_CALLS` (default `4`).
They are counted separately from telephony and web calls because each one holds a whole browser
in a container, which is far more expensive than either — and expensive in a resource neither
other cap accounts for. Exceeding the cap returns `503`.

The default is **not measured**. Set it from a load test that watches the connector containers.

### Deployment requirements

Meeting calls need three things on the host running the API:

| Setting | Purpose |
| :--- | :--- |
| `MEETING_CONNECTOR_IMAGE_GOOGLE_MEET` | Connector image to run. Defaults to `meeting-connector-google-meet:latest`. |
| `MEETING_CONNECTOR_STATUS_TOKEN` | Shared secret the connector authenticates its status callbacks with. **Meeting calls return 503 until this is set.** |
| `MEETING_CONNECTOR_STATUS_URL` | Where the connector posts status. Defaults to `<BACKEND_URL>/meeting_call/status`. |

The API launches connectors with `docker run`, so it needs access to a Docker daemon.

### Status callback (internal)

`POST /meeting_call/status` is called by the connector, not by customers. It authenticates with
the `X-Connector-Token` header carrying `MEETING_CONNECTOR_STATUS_TOKEN`, and rejects user API
keys. It is documented here only so that operators can recognise it in logs.
