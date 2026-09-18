"""Call-type vocabulary shared by the API and the agent worker.

Kept dependency-free for the same reason as ``src/core/model_support/``: the control image has
no ``livekit-agents`` and the agent image has no FastAPI, and both need these names.

Two orthogonal fields describe a call on ``CallRecord``:

* ``call_type`` is the *shape* of the call — how media reaches the room.
* ``call_service`` is the *provider* behind that shape (``exotel``, ``twilio``, ``google_meet``).

A meeting call is therefore ``call_type="meeting"`` with ``call_service="google_meet"``. Adding
Zoom later adds a member to :data:`MEETING_PLATFORMS` and nothing else here — the shape does not
change, only the provider.
"""

CALL_TYPE_OUTBOUND = "outbound"
CALL_TYPE_INBOUND = "inbound"
CALL_TYPE_WEB = "web"
CALL_TYPE_MEETING = "meeting"

#: Call types that do **not** run over a phone network. Everything else — including a missing
#: ``call_type`` on rows written before the field existed — is treated as telephony, which is the
#: safe direction to be wrong in: it only costs narrowband tuning and the scarcer capacity bucket.
NON_TELEPHONY_CALL_TYPES = frozenset({CALL_TYPE_WEB, CALL_TYPE_MEETING})

#: Meeting platforms the connector can join. One entry today; the value is also the
#: ``call_service`` stored on the ``CallRecord``.
MEETING_PLATFORM_GOOGLE_MEET = "google_meet"
MEETING_PLATFORMS = (MEETING_PLATFORM_GOOGLE_MEET,)


def is_phone_call(call_type: str | None) -> bool:
    """Whether this call's audio comes from a phone network.

    Drives narrowband noise reduction and the phone-tuned STT prompt. Meeting audio is
    wideband, so it must answer ``False`` here even though it is not a web call.
    """
    return call_type not in NON_TELEPHONY_CALL_TYPES
