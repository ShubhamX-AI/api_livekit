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
    "CreateApiKey",
    "CartesiaTTSConfig",
    "SarvamTTSConfig",
    "ElevenLabsVoiceSettings",
    "ElevenLabsTTSConfig",
    "MistralTTSConfig",
    "TTSConfig",
    "AssistantMode",
    "reject_retired_mode_key",
    "OPENAI_CASCADE_MODELS",
    "OPENAI_REALTIME_MODELS",
    "REASONING_EFFORT",
    "AssistantLLMConfig",
    "validate_mode_config",
    "NativeSTTConfig",
    "SarvamSTTConfig",
    "CartesiaSTTConfig",
    "DeepgramSTTConfig",
    "ElevenLabsSTTConfig",
    "OpenAISTTConfig",
    "STTConfig",
    "inject_provider_type",
    "inject_stt_config",
    "AssistantInteractionConfigSchema",
    "UpdateAssistantInteractionConfigSchema",
    "GreetingAudioSchema",
    "UpdateGreetingAudioSchema",
    "CreateAssistant",
    "UpdateAssistant",
    "TwilioTrunkConfig",
    "ExotelTrunkConfig",
    "TrunkConfig",
    "CreateOutboundTrunk",
    "TriggerOutboundCall",
    "TriggerPassthroughCall",
    "TriggerWebCall",
    "InboundTwilioConfig",
    "InboundExotelConfig",
    "InboundConfig",
    "AssignInboundNumber",
    "UpdateInboundMapping",
    "validate_inbound_context_url",
    "WebhookInboundContextStrategyConfigSchema",
    "UpdateWebhookInboundContextStrategyConfigSchema",
    "InboundContextStrategyConfig",
    "UpdateInboundContextStrategyConfig",
    "CreateInboundContextStrategy",
    "UpdateInboundContextStrategy",
    "ToolParameterSchema",
    "CreateTool",
    "UpdateTool",
    "AttachToolsRequest",
]
