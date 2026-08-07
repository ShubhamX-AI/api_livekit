from typing import Literal, Optional

from pydantic import BaseModel, Field


# Triggure Outbound call
class TriggerOutboundCall(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID (cannot be empty)")
    trunk_id: str = Field(..., min_length=1, max_length=100, description="Trunk ID (cannot be empty)")
    to_number: str = Field(..., min_length=1, max_length=100, description="To Number (cannot be empty)")
    call_service: Literal["twilio", "exotel"] = Field(..., description="Call service (cannot be empty)")
    metadata: Optional[dict] = Field(None, description="Metadata (optional)")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "assistant_id": "Test Assistant ID",
                "trunk_id": "Test Trunk ID",
                "to_number": "Test To Number",
                "call_service": "exotel",
                "metadata": {"extra": "value about the call"},
            }
        }


class TriggerPassthroughCall(BaseModel):
    """Initiates a passthrough call: web user ↔ SIP with no AI agent."""

    trunk_id: str = Field(..., min_length=1, max_length=100)
    to_number: str = Field(..., min_length=1, max_length=100)
    metadata: Optional[dict] = Field(None)

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "trunk_id": "trunk_abc123",
                "to_number": "+919876543210",
            }
        }


# Trigger Web Call
class TriggerWebCall(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID")
    metadata: Optional[dict] = Field(None, description="Optional metadata passed to the agent")
    text_only: bool = Field(False, description="Run as a text-only chat: no STT, no TTS, no recording. Pipeline-mode assistants only.")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "assistant_id": "Test Assistant ID",
                "metadata": {"extra": "value about the call"},
            }
        }
