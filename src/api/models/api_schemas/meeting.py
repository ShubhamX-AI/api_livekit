"""Schemas for meeting calls — an assistant joining a Google Meet (later Zoom, Teams)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.core.call_types import MEETING_PLATFORM_GOOGLE_MEET, MEETING_PLATFORMS

#: Pydantic needs a literal type, not a runtime tuple. Keeping the two in step is what this
#: assertion is for: adding a platform to MEETING_PLATFORMS without widening the Literal would
#: otherwise fail at request time instead of at import time.
MeetingPlatform = Literal["google_meet"]
assert set(MEETING_PLATFORMS) == set(MeetingPlatform.__args__), (
    "MeetingPlatform literal and call_types.MEETING_PLATFORMS have drifted apart"
)


class TriggerMeetingCall(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID")
    meeting_url: str = Field(..., min_length=1, max_length=500, description="URL of the meeting to join")
    platform: MeetingPlatform = Field(
        MEETING_PLATFORM_GOOGLE_MEET, description="Which meeting platform the URL belongs to"
    )
    bot_display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Name shown in the meeting participant list. Defaults to the assistant's name.",
    )
    metadata: Optional[dict] = Field(None, description="Optional metadata passed to the agent")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "assistant_id": "Test Assistant ID",
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "platform": "google_meet",
                "bot_display_name": "Sales Assistant",
                "metadata": {"extra": "value about the call"},
            }
        }


class MeetingConnectorStatus(BaseModel):
    """Posted by the connector container as it moves through the meeting's lifecycle.

    Authenticated with the shared MEETING_CONNECTOR_STATUS_TOKEN, not a user API key — the
    connector is infrastructure, not a customer.
    """

    room_name: str = Field(..., min_length=1, max_length=200, description="LiveKit room the connector was launched for")
    status: Literal["waiting", "joined", "failed", "ended"] = Field(..., description="Connector lifecycle state")
    detail: Optional[str] = Field(None, max_length=500, description="Human-readable reason, required in practice for 'failed'")

    class Config:
        str_strip_whitespace = True
