from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.core.agents.llm_capabilities import (
    CASCADE_MODELS,
    DEFAULT_CASCADE_MODEL,
    unsupported_knob_reason,
)
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
# reject realtime model names.
#
# The list itself lives in core/agents/llm_capabilities.py, split by family, because the
# same split decides which generation knobs each model accepts. Adding a model there is
# what adds it here. Keep both in sync with docs/architecture/cascade-pipeline.md and
# docs/reference/compatibility.md when OpenAI ships new models.
OPENAI_CASCADE_MODELS = CASCADE_MODELS

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

# Reasoning models take reasoning_effort and reject temperature, top_p and the penalties.
# Which models those are lives in core/agents/llm_capabilities.py. Values match
# openai.types.Reasoning.effort.
#
# The value set here is model-independent; the pairing with the selected model is checked
# below by _validate_cascade_knobs, and again at call time by the factory — a stored config
# outlives the model it was written for.
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
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="Provider API key override for the selected provider (openai or gemini).")

    # Generation knobs. These are applied to the cascade LLM (openai.responses.LLM);
    # they are harmless (ignored) in the realtime/pipeline modes. See
    # docs/api/assistant/index.md and the OpenAI LLM docs for valid values.
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature (0–2). Higher is more random. Reasoning models (gpt-5.x) reject it, so it is dropped before the call on those; set reasoning_effort instead. Only one of temperature or top_p may be set (responses API uses temperature).")
    max_output_tokens: Optional[int] = Field(None, gt=0, description="Cap on output tokens for the response (responses API `max_output_tokens`).")
    reasoning_effort: Optional[REASONING_EFFORT] = Field(None, description="Reasoning depth. A gpt-5 parameter: older models reject it, so it is dropped before the call on anything outside the gpt-5 line rather than sent and failed.")
    service_tier: Optional[_SERVICE_TIERS] = Field(None, description="OpenAI processing/billing tier: auto, default, flex, scale, priority.")
    verbosity: Optional[_VERBOSITY] = Field(None, description="Constrains response verbosity: low, medium, high. A gpt-5 parameter (`text.verbosity`), dropped before the call on older models — chat-latest counts as gpt-5 here.")
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


def _validate_cascade_knobs(llm_config, model) -> None:
    """Reject a generation knob the chosen cascade model cannot read.

    Without this the knob was accepted, stored, and then dropped (or worse, sent and 400'd)
    at call time — the operator saw a config field that did nothing. `has_tools` stays False
    here on purpose: whether function tools are attached is a property of the session, not
    of the config, so the tool-incompatible reasoning pairing is caught by the factory.
    """
    for knob in ("temperature", "reasoning_effort", "verbosity"):
        value = getattr(llm_config, knob, None)
        if value is None:
            continue
        reason = unsupported_knob_reason(model, knob)
        if reason:
            raise ValueError(
                f"assistant_llm_config.{knob} is not supported by model '{model}' — {reason}. "
                "See docs/reference/compatibility.md."
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
                "choose 'sarvam' (multilingual), 'cartesia', 'deepgram', 'elevenlabs' or 'openai'."
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
        if llm_config is not None:
            _validate_cascade_knobs(llm_config, model or DEFAULT_CASCADE_MODEL)
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
