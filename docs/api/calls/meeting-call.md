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
| `data.agent_dispatch` | object | The LiveKit agent dispatch that was created. |
| `data.connector_dispatch` | object | The LiveKit dispatch created for the meeting connector worker. |

### HTTP Status Codes

| Code | Description |
| :--- | :--- |
| 200 | Success - The assistant and connector worker were dispatched. |
| 400 | Bad Request - `meeting_url` is not a valid link for `platform`. |
| 422 | Validation Error - Invalid request body. |
| 401 | Unauthorized - Invalid or missing Bearer token. |
| 404 | Not Found - Assistant not found for the authenticated user. |
| 503 | Unavailable - `MAX_CONCURRENT_MEETING_CALLS` reached or the global session ceiling is reached. |
| 500 | Server Error - Internal error while starting the meeting call. |

### How it works

A meeting call is a web call whose participant happens to be a browser sitting in a meeting. The
LiveKit room, the agent dispatch, the `CallRecord`, the usage record and the end-of-call webhook
are all the same as a web call. The difference is who joins the room.

1. The API creates a LiveKit room and dispatches the `api-agent` assistant into it.
2. The API creates a second explicit dispatch for the configured
   `MEETING_CONNECTOR_AGENT_NAME` worker, passing the meeting URL, platform, and display name in
   job metadata.
3. The connector worker opens a browser, joins the meeting, and publishes the meeting's audio into
   the LiveKit room as a single participant named `google-meet`.
4. The assistant sets `lk.publish_on_behalf` to the room name. The connector subscribes to the
   participant carrying that attribute and plays its audio into the meeting.

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

The connector publishes JSON lifecycle events on the `meeting_connector_events` LiveKit data topic.
The connector also sets `lk.meeting_connector_status=ready` on its LiveKit participant. That
attribute lets the assistant recover readiness if the data event was published before the
assistant finished connecting. The assistant worker persists the events and moves the
`CallRecord` along:

| Connector reports | `call_status` |
| :--- | :--- |
| `waiting` | stays `initiated` — someone in the meeting has to admit the bot |
| `ready` | `answered`, with `answered_at` set |
| `failed` | `failed`, with the reason in `call_status_reason`, then the call is ended |
| `ended` | the assistant ends the room through the normal finalization path |

`CallRecord.call_type` is `"meeting"` and `call_service` is the platform (`"google_meet"`).

### Capacity

Meeting calls have their own concurrency cap, `MAX_CONCURRENT_MEETING_CALLS` (default `4`).
They are counted separately from telephony and web calls because each one holds a whole browser
worker, which is far more expensive than either — and expensive in a resource neither
other cap accounts for. Exceeding the cap returns `503`.

The default is **not measured**. Set it from a load test that watches connector worker jobs.

### Deployment requirements

Meeting calls need three things on the host running the API:

| Setting | Purpose |
| :--- | :--- |
| `MEETING_CONNECTOR_AGENT_NAME` | LiveKit dispatch name registered by the connector worker. Defaults to `meet-connector`. |
| `MEETING_CONNECTOR_JOIN_TIMEOUT_SECONDS` | Maximum time the connector participant may take to appear in the LiveKit room before the call is failed. A miss here is a dispatch or worker-capacity problem, not a slow human, so it fails fast. Defaults to `120`. |
| `MEETING_CONNECTOR_READY_TIMEOUT_SECONDS` | Maximum time the assistant waits for the connector's `ready` event before failing the call. This window covers a human admitting the bot from the Google Meet waiting room, so it must stay above the connector service's own waiting-room budget (300 seconds) — otherwise this deadline expires first and deletes the room out from under a connector that is still working. Defaults to `360`. |

The connector worker must be deployed and registered with LiveKit under the configured dispatch
name. The API does not need Docker access.

To modify that worker, or to build one for a meeting platform other than Google Meet, see
[Build a Meeting Connector](../../guides/meeting-connector.md) — it documents the job metadata this
endpoint sends, the audio track and lifecycle events the connector must publish, and the rules it
has to obey to stay audible.
