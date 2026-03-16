from datetime import datetime, timezone
from typing import Optional, Literal, Text, List, Dict
from beanie import Document, Indexed
from pydantic import BaseModel, Field, EmailStr
from pymongo import IndexModel
from pymongo.collation import Collation


# API key storage
class APIKey(Document):
    """API key model for Beanie ODM"""

    api_key: Indexed(str, unique=True)
    user_name: str
    org_name: Optional[str] = None
    user_email: Indexed(EmailStr, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    class Settings:
        name = "api_keys"  # Collection name in MongoDB


class AssistantInteractionConfig(BaseModel):
    """Configuration for how the assistant interacts with the user."""

    speaks_first: bool = True
    filler_words: bool = False
    silence_reprompts: bool = False
    silence_reprompt_interval: float = 10.0
    silence_max_reprompts: int = 2


# Assistant storage
class Assistant(Document):
    """Assistant model for Beanie ODM"""

    assistant_id: Indexed(str, unique=True)
    assistant_name: str
    assistant_description: Optional[str] = None
    assistant_tts_model: str
    assistant_tts_config: Dict = {}
    assistant_prompt: str = Field(default="")
    assistant_start_instruction: Optional[str] = None
    assistant_interaction_config: AssistantInteractionConfig = Field(default_factory=AssistantInteractionConfig)
    assistant_end_call_enabled: bool = False
    assistant_end_call_trigger_phrase: Optional[str] = None
    assistant_end_call_agent_message: Optional[str] = None
    assistant_end_call_url: Optional[str] = None
    assistant_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assistant_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assistant_created_by_email: EmailStr
    assistant_updated_by_email: EmailStr
    assistant_is_active: bool = True
    tool_ids: List[str] = []  # References to Tool.tool_id

    class Settings:
        name = "assistants"  # Collection name in MongoDB
        indexes = [
            IndexModel(
                [("assistant_name", 1)],
                collation=Collation(
                    locale="en",
                    strength=2
                )
            )
        ]




class OutboundSIP(Document):
    """Outbound SIP trunk model for Beanie ODM"""

    trunk_id: Indexed(str, unique=True)
    trunk_name: str
    trunk_type: str = "twilio"  # "twilio" or "exotel"
    trunk_config: Dict = {}   # Stores Twilio or Exotel specific config
    trunk_created_by_email: EmailStr
    trunk_updated_by_email: EmailStr
    trunk_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trunk_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trunk_is_active: bool = True

    class Settings:
        name = "outbound_sip"  # Collection name in MongoDB


class CallRecord(Document):
    room_name: Indexed(str, unique=True)
    assistant_id: str
    assistant_name: str
    to_number: str
    recording_path: Optional[str] = None
    transcripts: List[Dict] = []  # [{speaker, text, timestamp}]
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    call_duration_minutes: Optional[float] = None

    class Settings:
        name = "call_records"


class ToolParameter(BaseModel):
    """Single parameter definition for a tool."""

    name: str
    type: Literal["string", "number", "boolean", "object", "array"] = "string"
    description: Optional[str] = None
    required: bool = True
    enum: Optional[List[str]] = None


class Tool(Document):
    """Tool definition stored in MongoDB."""

    tool_id: Indexed(str, unique=True)
    tool_name: str  # e.g. "lookup_weather" (snake_case, unique per user)
    tool_description: str  # Docstring sent to the LLM
    tool_parameters: List[ToolParameter] = []
    tool_execution_type: Literal["webhook", "static_return"] = "webhook"
    tool_execution_config: Dict = {}  # {"url": "..."} or {"value": ...}
    tool_created_by_email: EmailStr
    tool_updated_by_email: EmailStr
    tool_created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_is_active: bool = True

    class Settings:
        name = "tools"  # Collection name in MongoDB


class ActivityLog(Document):
    """User-visible activity log — one record per notable event (tool call, webhook fire)."""

    user_email: Indexed(str)  # used to scope logs to the owning user
    log_type: Literal["tool_call", "end_call_webhook"]
    assistant_id: Optional[str] = None
    room_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["success", "error"]
    request_data: Optional[Dict] = None   # what was sent outbound
    response_data: Optional[Dict] = None  # what came back
    latency_ms: Optional[int] = None
    message: str  # human-readable one-liner

    class Settings:
        name = "activity_logs"
