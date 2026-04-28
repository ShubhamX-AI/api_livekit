from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, Literal, Union, Annotated, List, Any


# Model for creating API key
class CreateApiKey(BaseModel):
    user_name: str = Field(..., min_length=1, max_length=100, description="User's name (cannot be empty)")
    org_name: Optional[str] = Field(None, max_length=100, description="Organization name (optional)")
    user_email: EmailStr = Field(..., description="User's email address (cannot be empty)")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "user_name": "Shubham Halder",
                "org_name": "Indus Net Technologies",
                "user_email": "shubham@example.com",
            }
        }


# ── TTS Config sub-models ──────────────────────────
class CartesiaTTSConfig(BaseModel):
    type: Literal["cartesia"] = "cartesia"  # discriminator field
    voice_id: str = Field(..., min_length=1, max_length=100, description="Cartesia voice ID")
    api_key: Optional[str] = Field(None, min_length=1, max_length=100, description="Cartesia API key (optional, falls back to system key)")


class SarvamTTSConfig(BaseModel):
    type: Literal["sarvam"] = "sarvam"
    speaker: str = Field(..., max_length=30, description="Sarvam speaker identifier")
    target_language_code: str = Field("bn-IN", max_length=10, description="BCP-47 language code")
    api_key: Optional[str] = Field(None, min_length=1, max_length=100, description="Sarvam API key (optional, falls back to system key)")


class ElevenLabsTTSConfig(BaseModel):
    type: Literal["elevenlabs"] = "elevenlabs"
    voice_id: str = Field(..., min_length=1, max_length=100, description="ElevenLabs voice ID")
    api_key: Optional[str] = Field(None, min_length=1, max_length=100, description="ElevenLabs API key (optional, falls back to system key)")


class MistralTTSConfig(BaseModel):
    type: Literal["mistral"] = "mistral"
    voice_id: str = Field(..., min_length=1, max_length=100, description="Mistral voice ID")
    api_key: Optional[str] = Field(None, min_length=1, max_length=100, description="Mistral API key (optional, falls back to system key)")


# ── Assistant LLM Config sub-model ───────────────────
class AssistantLLMConfig(BaseModel):
    provider: Optional[Literal["gemini"]] = Field(
        None,
        description="Realtime provider. Supported today: gemini. Ignored in pipeline mode.",
    )
    model: Optional[str] = Field(
        None,
        description="Realtime model override. Ignored in pipeline mode.",
    )
    voice: Optional[str] = Field(
        None,
        description="Realtime voice override. Ignored in pipeline mode.",
    )
    api_key: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Provider API key override. In pipeline mode this overrides the OpenAI key; in realtime mode it overrides the Gemini key.",
    )


# Discriminated union type
TTSConfig = Annotated[
    Union[CartesiaTTSConfig, SarvamTTSConfig, ElevenLabsTTSConfig, MistralTTSConfig],
    Field(discriminator="type"),  # discriminated by type field in parent
]


# ── Interaction Config sub-models ──────────────────
class AssistantInteractionConfigSchema(BaseModel):
    speaks_first: bool = Field(True, description="If True (default), assistant speaks first. If False, assistant stays silent and waits for the user to speak.")
    filler_words: bool = Field(False, description="Enable filler words while the user is speaking")
    silence_reprompts: bool = Field(False, description="Enable silence reprompts when the user stops responding")
    silence_reprompt_interval: float = Field(10.0, ge=1.0, le=60.0, description="Interval in seconds between silence reprompts")
    silence_max_reprompts: int = Field(2, ge=0, le=5, description="Maximum number of silence reprompts before ending the session")
    background_sound_enabled: bool = Field(True, description="Enable background ambience during the session")
    thinking_sound_enabled: bool = Field(True, description="Enable the typing-style thinking sound while the assistant is processing")
    allow_interruptions: bool = Field(False, description="Allow user to interrupt the assistant's initial greeting. Default False (interruptions blocked).")
    preferred_languages: Optional[List[str]] = Field(None, description="BCP-47 language codes the agent supports (e.g. ['hi-IN', 'en-US', 'ta-IN']). Speaker may switch between these. If unset, model auto-detects all languages.")


class UpdateAssistantInteractionConfigSchema(BaseModel):
    speaks_first: Optional[bool] = Field(None, description="If True, assistant speaks first. If False, assistant waits for user.")
    filler_words: Optional[bool] = Field(None, description="Enable or disable filler words")
    silence_reprompts: Optional[bool] = Field(None, description="Enable or disable silence reprompts")
    silence_reprompt_interval: Optional[float] = Field(None, ge=1.0, le=60.0, description="Interval in seconds between silence reprompts")
    silence_max_reprompts: Optional[int] = Field(None, ge=0, le=5, description="Maximum number of silence reprompts before ending the session")
    background_sound_enabled: Optional[bool] = Field(None, description="Enable or disable background ambience")
    thinking_sound_enabled: Optional[bool] = Field(None, description="Enable or disable the typing-style thinking sound")
    allow_interruptions: Optional[bool] = Field(None, description="Enable or disable user interruptions during assistant's initial greeting")
    preferred_languages: Optional[List[str]] = Field(None, description="BCP-47 language codes the agent supports (e.g. ['hi-IN', 'en-US', 'ta-IN']). Speaker may switch between these. Pass empty list to clear.")


# For Assistant creation
class CreateAssistant(BaseModel):
    assistant_name: str = Field(..., min_length=1, max_length=100, description="Assistant's name (cannot be empty)")
    assistant_description: str = Field(..., description="Assistant's description (optional)")
    assistant_prompt: str = Field(..., description="Assistant's prompt (cannot be empty)")
    assistant_llm_mode: Literal["pipeline", "realtime"] = Field("pipeline", description="LLM pipeline mode: pipeline (separate TTS) or realtime (model handles STT+LLM+TTS)")
    assistant_llm_config: Optional[AssistantLLMConfig] = Field(None,description="Shared LLM config. Optional in pipeline mode (supports api_key override). Required in realtime mode.",)
    assistant_tts_model: Optional[Literal["cartesia", "sarvam", "elevenlabs", "mistral"]] = Field(None, description="TTS Provider (required for pipeline mode)")
    assistant_tts_config: Optional[TTSConfig] = Field(None, description="TTS Configuration object (required for pipeline mode)")
    assistant_start_instruction: Optional[str] = Field(None, max_length=200, description="Assistant's start instruction")
    assistant_interaction_config: AssistantInteractionConfigSchema = Field(default_factory=AssistantInteractionConfigSchema, description="Interaction settings for the assistant")
    assistant_end_call_enabled: bool = Field(False, description="Enable built-in end_call tool")
    assistant_end_call_trigger_phrase: Optional[str] = Field(None, max_length=300, description="Example user phrase that should trigger end_call")
    assistant_end_call_agent_message: Optional[str] = Field(None, max_length=300, description="What assistant should say before ending the call")
    assistant_end_call_url: Optional[str] = Field(None, max_length=200, description="Assistant's end call url")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "examples": [
                {
                    "summary": "Pipeline mode (separate TTS)",
                    "value": {
                        "assistant_name": "Test Assistant",
                        "assistant_description": "Test Assistant Description(Optional)",
                        "assistant_prompt": "You are a helpful assistant.",
                        "assistant_llm_mode": "pipeline",
                        "assistant_llm_config": {
                            "api_key": "sk-..."
                        },
                        "assistant_tts_model": "cartesia",
                        "assistant_tts_config": {
                            "voice_id": "a167e0f3-df7e-4277-976b-be2f952fa275"
                        },
                        "assistant_start_instruction": "Start instruction.",
                        "assistant_interaction_config": {
                            "speaks_first": True,
                            "filler_words": True,
                            "silence_reprompts": True,
                            "silence_reprompt_interval": 10.0,
                            "silence_max_reprompts": 2,
                            "background_sound_enabled": True,
                            "thinking_sound_enabled": True,
                        },
                        "assistant_end_call_enabled": True,
                        "assistant_end_call_trigger_phrase": "Thanks, that's all. You can end the call now.",
                        "assistant_end_call_agent_message": "Thank you for your time. Have a great day.",
                        "assistant_end_call_url": "End call url.",
                    },
                },
                {
                    "summary": "Realtime mode (Gemini handles STT+LLM+TTS)",
                    "value": {
                        "assistant_name": "Gemini Assistant",
                        "assistant_description": "Full realtime assistant",
                        "assistant_prompt": "You are a helpful assistant.",
                        "assistant_llm_mode": "realtime",
                        "assistant_llm_config": {
                            "provider": "gemini",
                            "model": "gemini-3.1-flash-live-preview",
                            "voice": "Puck",
                        },
                    },
                },
            ]
        }

    @model_validator(mode="before")
    @classmethod
    def inject_tts_type(cls, data: dict):
        """Inject the `type` discriminator into tts_config so Pydantic picks the right model."""
        if isinstance(data, dict):
            model = data.get("assistant_tts_model")
            config = data.get("assistant_tts_config")
            if model and isinstance(config, dict):
                config["type"] = model
        return data

    @model_validator(mode="after")
    def validate_mode_fields(self):
        """Validate fields based on llm_mode."""
        if self.assistant_llm_mode == "pipeline":
            if not self.assistant_tts_model:
                raise ValueError("assistant_tts_model is required when assistant_llm_mode is 'pipeline'")
            if not self.assistant_tts_config:
                raise ValueError("assistant_tts_config is required when assistant_llm_mode is 'pipeline'")
        elif self.assistant_llm_mode == "realtime":
            if not self.assistant_llm_config:
                raise ValueError("assistant_llm_config is required when assistant_llm_mode is 'realtime'")
        if self.assistant_end_call_enabled:
            if not self.assistant_end_call_trigger_phrase:
                raise ValueError("assistant_end_call_trigger_phrase is required when assistant_end_call_enabled is True")
            if not self.assistant_end_call_agent_message:
                raise ValueError("assistant_end_call_agent_message is required when assistant_end_call_enabled is True")
        return self


# For Assistant update
class UpdateAssistant(BaseModel):
    assistant_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Assistant's name (optional)")
    assistant_description: Optional[str] = Field(None, description="Assistant's description (optional)")
    assistant_prompt: Optional[str] = Field(None, description="Assistant's prompt (optional)")
    assistant_llm_mode: Optional[Literal["pipeline", "realtime"]] = Field(None, description="LLM pipeline mode. When switching to 'pipeline', any stored realtime llm_config is cleared automatically unless you provide a new one.")
    assistant_llm_config: Optional[AssistantLLMConfig] = Field(None, description="Shared LLM config. In pipeline mode only api_key is used (overrides system OPENAI_API_KEY); in realtime mode provider/model/voice/api_key are supported.")
    assistant_tts_model: Optional[Literal["cartesia", "sarvam", "elevenlabs", "mistral"]] = Field(None, description="TTS Provider. Required when switching to pipeline mode only if no TTS config is already stored on the assistant.")
    assistant_tts_config: Optional[TTSConfig] = Field(None, description="TTS Configuration object (optional)")
    assistant_start_instruction: Optional[str] = Field(None, max_length=200, description="Assistant's start instruction (optional)")
    assistant_interaction_config: Optional[UpdateAssistantInteractionConfigSchema] = Field(None, description="Update interaction settings")
    assistant_end_call_enabled: Optional[bool] = Field(None, description="Enable/disable built-in end_call tool")
    assistant_end_call_trigger_phrase: Optional[str] = Field(None, max_length=300, description="Example user phrase that should trigger end_call")
    assistant_end_call_agent_message: Optional[str] = Field(None, max_length=300, description="What assistant should say before ending the call")
    assistant_end_call_url: Optional[str] = Field(None, max_length=200, description="Assistant's end call url (optional)")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "assistant_name": "Updated Assistant Name",
                "assistant_interaction_config": {
                    "speaks_first": False,
                    "filler_words": True,
                    "silence_reprompts": False,
                    "background_sound_enabled": False,
                    "thinking_sound_enabled": True,
                },
                "assistant_end_call_enabled": True,
                "assistant_end_call_trigger_phrase": "Okay bye, please end the call.",
                "assistant_end_call_agent_message": "Goodbye, and thank you for speaking with us.",
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_tts_type(cls, data: dict):
        """Same injection for updates."""
        if isinstance(data, dict):
            model = data.get("assistant_tts_model")
            config = data.get("assistant_tts_config")
            if model and isinstance(config, dict):
                config["type"] = model
        return data

    @model_validator(mode="after")
    def validate_update_consistency(self):
        """Validate TTS and LLM config consistency on update."""
        # TTS fields must come in pairs
        if bool(self.assistant_tts_model) != bool(self.assistant_tts_config):
            raise ValueError(
                "Provide both `assistant_tts_model` and `assistant_tts_config` together, or neither."
            )
        # Switching to realtime requires llm_config
        if self.assistant_llm_mode == "realtime" and not self.assistant_llm_config:
            raise ValueError(
                "assistant_llm_config is required when switching to realtime mode."
            )
        return self


# ── SIP Trunk Config sub-models ────────────────────────
class TwilioTrunkConfig(BaseModel):
    address: str = Field(
        ..., min_length=1, max_length=100, description="SIP trunk address"
    )
    numbers: List[str] = Field(..., description="SIP trunk numbers")
    username: str = Field(
        ..., min_length=1, max_length=100, description="SIP auth username"
    )
    password: str = Field(
        ..., min_length=1, max_length=100, description="SIP auth password"
    )


class ExotelTrunkConfig(BaseModel):
    exotel_number: str = Field(..., min_length=1, max_length=20, description="Exotel virtual number (caller ID)")
    # Optional overrides for advanced setup
    sip_host: Optional[str] = Field(None, description="Exotel SIP proxy host")
    sip_port: Optional[int] = Field(None, description="Exotel SIP proxy port")
    sip_domain: Optional[str] = Field(None, description="Exotel SIP domain")


# Discriminated union type for Trunks
TrunkConfig = Annotated[
    Union[TwilioTrunkConfig, ExotelTrunkConfig],
    Field(discriminator=None),  # discriminated by trunk_type in parent
]


# For Outbound Trunk creation
class CreateOutboundTrunk(BaseModel):
    trunk_name: str = Field(..., min_length=1, max_length=100, description="Trunk name (cannot be empty)")
    trunk_type: Literal["twilio", "exotel"] = Field(..., description="Trunk type")
    trunk_config: TrunkConfig = Field(..., description="Trunk configuration object (varies by type)")

    class Config:
        # Strip whitespace from string fields
        str_strip_whitespace = True
        # Example for API documentation
        json_schema_extra = {
            "example": {
                "trunk_name": "My Exotel Trunk",
                "trunk_type": "exotel",
                "trunk_config": {"exotel_number": "08044319240"},
            }
        }

    @model_validator(mode="after")
    def validate_trunk_config_matches_type(self):
        expected = {
            "twilio": TwilioTrunkConfig,
            "exotel": ExotelTrunkConfig,
        }
        if not isinstance(self.trunk_config, expected[self.trunk_type]):
            raise ValueError(f"trunk_config must match trunk_type '{self.trunk_type}'")
        return self


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


# Trigger Web Call
class TriggerWebCall(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID")
    metadata: Optional[dict] = Field(None, description="Optional metadata passed to the agent")

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


# Incoming Call Config

class InboundTwilioConfig(BaseModel):
    type: Literal["twilio"]
    phone_number: str = Field(..., min_length=1, max_length=30, description="Twilio inbound phone number")

class InboundExotelConfig(BaseModel):
    type: Literal["exotel"]
    phone_number: str = Field(..., min_length=1, max_length=30, description="Exotel inbound phone number")

InboundConfig = Annotated[
    Union[InboundTwilioConfig, InboundExotelConfig],
    Field(discriminator="type"),
]

class AssignInboundNumber(BaseModel):
    assistant_id: str = Field(..., min_length=1, max_length=100, description="Assistant ID")
    inbound_context_strategy_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional inbound context strategy ID")
    service: Literal["exotel", "twilio"] = Field(..., description="Inbound service")
    inbound_config: InboundConfig = Field(..., description="Configuration object based on service type")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "assistant_id": "Test Assistant ID",
                "inbound_context_strategy_id": "strategy-123",
                "service": "exotel",
                "inbound_config": {
                    "type": "exotel",
                    "phone_number": "+918044319240"
                }
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_type_into_config(cls, data: Any) -> Any:
        if isinstance(data, dict):
            service = data.get("service")
            config = data.get("inbound_config")
            
            if service and isinstance(config, dict) and "type" not in config:
                # Mirror the top-level service to the config object's type
                config["type"] = service
                
        return data

    @model_validator(mode="after")
    def validate_service_matches_config(self):
        # We check again after parsing to ensure everything is consistent
        if self.service != self.inbound_config.type:
            raise ValueError(f"service '{self.service}' must match inbound_config.type '{self.inbound_config.type}'")
        return self


class UpdateInboundMapping(BaseModel):
    assistant_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Assistant ID")
    inbound_context_strategy_id: Optional[str] = Field( None, min_length=1, max_length=100, description="Optional inbound context strategy ID; send null to detach")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "assistant_id": "Updated Assistant ID",
                "inbound_context_strategy_id": "strategy-123",
            }
        }

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


# Inbound Context Strategy Schemas
class WebhookInboundContextStrategyConfigSchema(BaseModel):
    type: Literal["webhook"] = "webhook"
    url: str = Field(..., min_length=1, max_length=500, description="Webhook URL used to fetch inbound caller context")
    headers: dict[str, str] = Field(default_factory=dict, description="Optional headers sent with the inbound context webhook")
    timeout_seconds: float = Field(2.0, ge=0.5, le=10.0, description="Webhook timeout in seconds")


class UpdateWebhookInboundContextStrategyConfigSchema(BaseModel):
    type: Literal["webhook"] = "webhook"
    url: Optional[str] = Field(None, min_length=1, max_length=500, description="Webhook URL used to fetch inbound caller context")
    headers: Optional[dict[str, str]] = Field(None, description="Optional headers sent with the inbound context webhook")
    timeout_seconds: Optional[float] = Field(None, ge=0.5, le=10.0, description="Webhook timeout in seconds")


InboundContextStrategyConfig = Annotated[
    WebhookInboundContextStrategyConfigSchema,
    Field(discriminator="type"),
]


UpdateInboundContextStrategyConfig = Annotated[
    UpdateWebhookInboundContextStrategyConfigSchema,
    Field(discriminator="type"),
]


class CreateInboundContextStrategy(BaseModel):
    strategy_name: str = Field(..., min_length=1, max_length=100, description="Strategy name")
    strategy_type: Literal["webhook"] = Field(..., description="Strategy type")
    strategy_config: InboundContextStrategyConfig = Field(..., description="Typed strategy config")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "strategy_name": "CRM lookup",
                "strategy_type": "webhook",
                "strategy_config": {
                    "url": "https://example.com/caller-context",
                    "headers": {
                        "Authorization": "Bearer demo-token"
                    },
                    "timeout_seconds": 2.0
                },
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_strategy_type(cls, data: dict):
        if isinstance(data, dict):
            strategy_type = data.get("strategy_type")
            config = data.get("strategy_config")
            if strategy_type and isinstance(config, dict):
                config["type"] = strategy_type
        return data


class UpdateInboundContextStrategy(BaseModel):
    strategy_name: Optional[str] = Field(None, min_length=1, max_length=100, description="Strategy name")
    strategy_type: Optional[Literal["webhook"]] = Field(None, description="Strategy type")
    strategy_config: Optional[UpdateInboundContextStrategyConfig] = Field(None, description="Typed strategy config")

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "strategy_name": "CRM lookup v2",
                "strategy_type": "webhook",
                "strategy_config": {
                    "url": "https://example.com/caller-context-v2",
                    "timeout_seconds": 2.0
                },
            }
        }

    @model_validator(mode="before")
    @classmethod
    def inject_strategy_type(cls, data: dict):
        if isinstance(data, dict):
            strategy_type = data.get("strategy_type")
            config = data.get("strategy_config")
            if strategy_type and isinstance(config, dict):
                config["type"] = strategy_type
        return data

    @model_validator(mode="after")
    def validate_strategy_update(self):
        if not self.model_fields_set:
            raise ValueError("No fields provided for update")
        if bool(self.strategy_type) != bool(self.strategy_config):
            raise ValueError(
                "Provide both `strategy_type` and `strategy_config` together, or neither."
            )
        return self


# ---- Tool Schemas ----


class ToolParameterSchema(BaseModel):
    """Parameter definition for a tool."""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Parameter name"
    )
    type: Literal["string", "number", "boolean", "object", "array"] = Field(
        "string", description="Parameter data type"
    )
    description: Optional[str] = Field(
        None, max_length=300, description="Parameter description for the LLM"
    )
    required: bool = Field(True, description="Whether the parameter is required")
    enum: Optional[List[str]] = Field(
        None, description="Allowed values (only for string type)"
    )


class CreateTool(BaseModel):
    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z_][a-z0-9_]*$",
        description="Tool name in snake_case (e.g. lookup_weather)",
    )
    tool_description: str = Field(
        ..., min_length=1, max_length=500, description="What the tool does (shown to LLM)"
    )
    tool_parameters: List[ToolParameterSchema] = Field(
        default=[], description="Tool parameter definitions"
    )
    tool_execution_type: Literal["webhook", "static_return"] = Field(
        ..., description="How the tool executes: 'webhook' (HTTP POST) or 'static_return' (fixed value)"
    )
    tool_execution_config: dict = Field(
        ...,
        description="Execution config: {'url': '...'} for webhook, {'value': ...} for static_return",
    )

    class Config:
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "tool_name": "lookup_weather",
                "tool_description": "Look up weather information for a given location",
                "tool_parameters": [
                    {
                        "name": "location",
                        "type": "string",
                        "description": "City name to look up",
                        "required": True,
                    }
                ],
                "tool_execution_type": "webhook",
                "tool_execution_config": {"url": "https://api.example.com/weather"},
            }
        }


class UpdateTool(BaseModel):
    tool_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z_][a-z0-9_]*$",
        description="Tool name in snake_case",
    )
    tool_description: Optional[str] = Field(
        None, min_length=1, max_length=500, description="What the tool does"
    )
    tool_parameters: Optional[List[ToolParameterSchema]] = Field(
        None, description="Tool parameter definitions"
    )
    tool_execution_type: Optional[Literal["webhook", "static_return"]] = Field(
        None, description="Execution type"
    )
    tool_execution_config: Optional[dict] = Field(None, description="Execution config")

    class Config:
        str_strip_whitespace = True


class AttachToolsRequest(BaseModel):
    tool_ids: List[str] = Field(
        ..., min_length=1, description="List of tool IDs to attach/detach"
    )
