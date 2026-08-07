from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.core.providers.keys import ProviderApiKey

# ── Runtime mode ────────────────────────────────────
# Selects the shape of the whole session (which stages exist, plugin vs. one realtime
# model) — not an LLM choice. That lives in AssistantLLMConfig.provider/model below.
AssistantMode = Literal["pipeline", "realtime", "cascade"]

_RETIRED_MODE_KEY_ERROR = (
    "`assistant_llm_mode` has been renamed to `assistant_mode`. Update your request."
)


def reject_retired_mode_key(data: dict) -> None:
    if isinstance(data, dict) and "assistant_llm_mode" in data:
        raise ValueError(_RETIRED_MODE_KEY_ERROR)


# ── OpenAI cascade LLM models ────────────────────────
# The non-realtime OpenAI chat/test models accepted in cascade mode. The `model`
# field is shared with the realtime/pipeline modes (which use realtime model IDs
# like "gpt-realtime-1.5" or Gemini), so the allowlist is enforced only inside the
# cascade validator rather than as a Literal on the shared field — that would
# reject realtime model names. Keep this list in sync with
# docs/architecture/cascade-pipeline.md when OpenAI ships new models.
OPENAI_CASCADE_MODELS = frozenset(
    {
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5.1",
        "gpt-5.1-chat-latest",
        "gpt-5.2",
        "gpt-5.2-chat-latest",
        "gpt-5.3-chat-latest",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5.5",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "chat-latest",
        "gpt-oss-120b",
    }
)

# ── OpenAI realtime models (pipeline + realtime modes) ──
# Pipeline and realtime both build an `openai.realtime.RealtimeModel`, which only speaks
# to the Realtime API. Passing a chat model such as "gpt-4.1" there used to be accepted at
# create time and then failed to connect at call time, so the two allowlists are kept
# separate and each mode checks its own. Add new realtime IDs here as OpenAI ships them.
OPENAI_REALTIME_MODELS = frozenset(
    {
        "gpt-realtime",
        "gpt-realtime-1.5",
        "gpt-realtime-mini",
        "gpt-4o-realtime-preview",
        "gpt-4o-mini-realtime-preview",
    }
)

# The gpt-5.x line (and gpt-5.1+) are reasoning models: they reject temperature,
# top_p and the penalties, and use reasoning_effort instead. Used to guide users
# and to keep configs safe. Matches openai.types.Reasoning.effort.
REASONING_EFFORT = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
_SERVICE_TIERS = Literal["auto", "default", "flex", "scale", "priority"]
_VERBOSITY = Literal["low", "medium", "high"]
_RESPONSES_TOOL_CHOICE = Literal["auto", "required", "none"]


# ── Assistant LLM Config sub-model ───────────────────
class AssistantLLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Optional[Literal["gemini", "openai"]] = Field(None, description="LLM vendor. 'openai' in pipeline and cascade mode (the only value accepted there); 'gemini' (default) or 'openai' in realtime mode. Defaults to openai in pipeline/cascade and gemini in realtime.")
    model: Optional[str] = Field(None, description="Model override for the selected provider. Validated per mode: an OpenAI realtime ID in pipeline/realtime mode, an allowlisted OpenAI chat model in cascade mode. Gemini realtime model IDs are not validated.")
    voice: Optional[str] = Field(None, description="Voice override. Used when the model speaks its own audio (realtime mode).")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=200, description="Provider API key override for the selected provider (openai or gemini).")

    # Generation knobs. These are applied to the cascade LLM (openai.responses.LLM);
    # they are harmless (ignored) in the realtime/pipeline modes. See
    # docs/api/assistant/index.md and the OpenAI LLM docs for valid values.
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature (0–2). Higher is more random. Ignored by reasoning models (gpt-5.x). Only one of temperature or top_p may be set (responses API uses temperature).")
    max_output_tokens: Optional[int] = Field(None, gt=0, description="Cap on output tokens for the response (responses API `max_output_tokens`).")
    reasoning_effort: Optional[REASONING_EFFORT] = Field(None, description="Reasoning depth. Only applied to reasoning models (gpt-5, gpt-5.x). Ignored elsewhere.")
    service_tier: Optional[_SERVICE_TIERS] = Field(None, description="OpenAI processing/billing tier: auto, default, flex, scale, priority.")
    verbosity: Optional[_VERBOSITY] = Field(None, description="Constrains response verbosity: low, medium, high.")
    tool_choice: Optional[_RESPONSES_TOOL_CHOICE] = Field(None, description="How the model uses tools in cascade mode: auto, required or none.")
    parallel_tool_calls: Optional[bool] = Field(None, description="Allow the model to make multiple tool calls in a single response.")


# Rejecting Gemini in pipeline mode: LiveKit's half-cascade pattern needs the realtime
# model in a text-only modality, and Google's Live API only supports that on
# non-native-audio models (https://github.com/googleapis/python-genai/issues/1780). The
# Live models we would actually want are native-audio, and the 3.1 line additionally
# ignores generate_reply()/update_instructions(), which the greeting and agent-handoff
# paths depend on. Gemini remains fully supported in realtime mode.
PIPELINE_GEMINI_ERROR = (
    "assistant_llm_config.provider 'gemini' is not supported in pipeline mode — "
    "Google's Live API cannot run the text-only (half-cascade) modality on its "
    "native-audio models. Use assistant_mode 'realtime' for Gemini, or provider "
    "'openai' in pipeline mode. See docs/reference/compatibility.md."
)


def validate_mode_config(mode, llm_config, stt_model) -> None:
    """Reject provider/model/STT combinations the runtime cannot actually run.

    One rule table for all three modes, shared by the create and update validators so a
    combination is rejected with a 422 at the API rather than accepted and then failing at
    job start with only a log line. The runtime counterparts are
    src/core/agents/session.py (pipeline/realtime) and src/core/agents/llm/factory.py
    plus src/core/agents/stt/factory.py (cascade). Keep both in sync, and keep
    docs/reference/compatibility.md in sync with both.
    """
    provider = getattr(llm_config, "provider", None)
    model = getattr(llm_config, "model", None)

    if mode == "cascade":
        # Cascade runs a plain LLM, so there is no realtime model to speak its own audio
        # or transcribe itself: 'native' STT is meaningless, and only OpenAI is wired up
        # as a non-realtime LLM (see src/core/agents/llm/factory.py).
        if stt_model == "native":
            raise ValueError(
                "assistant_stt_model 'native' is not valid in cascade mode — "
                "choose 'sarvam' (multilingual), 'cartesia', 'deepgram' or 'elevenlabs'."
            )
        if provider and provider != "openai":
            raise ValueError(
                f"assistant_llm_config.provider '{provider}' is not supported in cascade mode — "
                "cascade supports 'openai' only."
            )
        if model and model not in OPENAI_CASCADE_MODELS:
            raise ValueError(
                f"assistant_llm_config.model '{model}' is not supported in cascade mode — "
                "must be one of the documented OpenAI models: "
                f"{', '.join(sorted(OPENAI_CASCADE_MODELS))}."
            )
        return

    if mode == "pipeline":
        if provider and provider != "openai":
            raise ValueError(PIPELINE_GEMINI_ERROR)
        if model and model not in OPENAI_REALTIME_MODELS:
            raise ValueError(
                f"assistant_llm_config.model '{model}' is not a realtime model — "
                "pipeline mode drives the OpenAI Realtime API, so the model must be one "
                f"of: {', '.join(sorted(OPENAI_REALTIME_MODELS))}. Chat models such as "
                "'gpt-4.1' belong to cascade mode."
            )
        return

    if mode == "realtime":
        # Both vendors work here. Model IDs are deliberately not checked: Gemini ships new
        # Live IDs frequently and an allowlist would block them the day they land.
        if provider == "openai" and model and model not in OPENAI_REALTIME_MODELS:
            raise ValueError(
                f"assistant_llm_config.model '{model}' is not an OpenAI realtime model — "
                f"must be one of: {', '.join(sorted(OPENAI_REALTIME_MODELS))}."
            )
