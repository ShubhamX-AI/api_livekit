"""API request/response schemas, split by domain. Import from here as before —
`from src.api.models.api_schemas import X` keeps working unchanged.
"""

from .assistant import (
    CreateAssistant,
    UpdateAssistant,
    inject_provider_type,
    inject_stt_config,
)
from .config.interaction_config import (
    AssistantInteractionConfigSchema,
    GreetingAudioSchema,
    UpdateAssistantInteractionConfigSchema,
    UpdateGreetingAudioSchema,
)
from .config.llm_config import (
    OPENAI_CASCADE_MODELS,
    OPENAI_REALTIME_MODELS,
    REASONING_EFFORT,
    AssistantLLMConfig,
    AssistantMode,
    reject_retired_mode_key,
    validate_mode_config,
)
from .config.stt_config import (
    CartesiaSTTConfig,
    DeepgramSTTConfig,
    ElevenLabsSTTConfig,
    NativeSTTConfig,
    OpenAISTTConfig,
    SarvamSTTConfig,
    STTConfig,
)
from .config.tts_config import (
    CartesiaTTSConfig,
    ElevenLabsTTSConfig,
    ElevenLabsVoiceSettings,
    MistralTTSConfig,
    SarvamTTSConfig,
    TTSConfig,
)
from .keys import CreateApiKey
from .meeting import TriggerMeetingCall
from .telephony.calls import TriggerOutboundCall, TriggerPassthroughCall, TriggerWebCall
from .telephony.inbound import (
    AssignInboundNumber,
    InboundConfig,
    InboundExotelConfig,
    InboundTwilioConfig,
    UpdateInboundMapping,
)
from .telephony.inbound_context_strategy import (
    CreateInboundContextStrategy,
    InboundContextStrategyConfig,
    UpdateInboundContextStrategy,
    UpdateInboundContextStrategyConfig,
    UpdateWebhookInboundContextStrategyConfigSchema,
    WebhookInboundContextStrategyConfigSchema,
    validate_inbound_context_url,
)
from .telephony.trunk import (
    CreateOutboundTrunk,
    ExotelTrunkConfig,
    TrunkConfig,
    TwilioTrunkConfig,
)
from .tools import AttachToolsRequest, CreateTool, ToolParameterSchema, UpdateTool

__all__ = [
    "OPENAI_CASCADE_MODELS",
    "OPENAI_REALTIME_MODELS",
    "REASONING_EFFORT",
    "AssignInboundNumber",
    "AssistantInteractionConfigSchema",
    "AssistantLLMConfig",
    "AssistantMode",
    "AttachToolsRequest",
    "CartesiaSTTConfig",
    "CartesiaTTSConfig",
    "CreateApiKey",
    "CreateAssistant",
    "CreateInboundContextStrategy",
    "CreateOutboundTrunk",
    "CreateTool",
    "DeepgramSTTConfig",
    "ElevenLabsSTTConfig",
    "ElevenLabsTTSConfig",
    "ElevenLabsVoiceSettings",
    "ExotelTrunkConfig",
    "GreetingAudioSchema",
    "InboundConfig",
    "InboundContextStrategyConfig",
    "InboundExotelConfig",
    "InboundTwilioConfig",
    "MistralTTSConfig",
    "NativeSTTConfig",
    "OpenAISTTConfig",
    "STTConfig",
    "SarvamSTTConfig",
    "SarvamTTSConfig",
    "TTSConfig",
    "ToolParameterSchema",
    "TriggerMeetingCall",
    "TriggerOutboundCall",
    "TriggerPassthroughCall",
    "TriggerWebCall",
    "TrunkConfig",
    "TwilioTrunkConfig",
    "UpdateAssistant",
    "UpdateAssistantInteractionConfigSchema",
    "UpdateGreetingAudioSchema",
    "UpdateInboundContextStrategy",
    "UpdateInboundContextStrategyConfig",
    "UpdateInboundMapping",
    "UpdateTool",
    "UpdateWebhookInboundContextStrategyConfigSchema",
    "WebhookInboundContextStrategyConfigSchema",
    "inject_provider_type",
    "inject_stt_config",
    "reject_retired_mode_key",
    "validate_inbound_context_url",
    "validate_mode_config",
]
