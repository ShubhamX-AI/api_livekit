"""Factory for the conversational LLM used in cascade mode.

Only cascade mode needs this. The `pipeline` and `realtime` modes build a
`RealtimeModel` inline in session.py, because their LLM also owns STT (and, in
realtime, TTS) — there is nothing to factor out. Cascade is the only mode where
the LLM is a standalone stage.
"""

from livekit.plugins import openai
from openai.types import Reasoning

from src.core.config import settings
from src.core.logger import logger

# Kept as a plain string default, not a Literal. OpenAI ships models monthly and a
# Literal would mean a deploy per model; the supported set is documented instead
# (docs/architecture/cascade-pipeline.md).
DEFAULT_MODEL = "gpt-4.1"


def create_llm(assistant):
    """Build a non-realtime LLM from the assistant's LLM config. Returns None on error."""
    llm_config = assistant.assistant_llm_config or {}
    provider = (llm_config.get("provider") or "openai").lower()
    assistant_id = assistant.assistant_id

    if provider != "openai":
        logger.error(
            f"Unsupported cascade LLM provider {provider!r} for assistant {assistant_id} "
            "— cascade mode supports 'openai' only"
        )
        return None

    api_key = llm_config.get("api_key") or settings.OPENAI_API_KEY
    if not api_key:
        logger.error(f"No OpenAI API key for cascade assistant {assistant_id}")
        return None

    # responses.LLM is the recommended surface for the direct OpenAI API: cheaper than
    # chat-completions, and the same @function_tool contract, so DB-backed tools work
    # unchanged. openai.LLM stays the path for OpenAI-compatible third-party endpoints,
    # which this platform does not use.
    kwargs: dict = {
        "model": llm_config.get("model") or DEFAULT_MODEL,
        "api_key": api_key,
    }

    # Generation knobs from assistant_llm_config — forwarded only when explicitly set in
    # config, so omitted knobs keep the SDK defaults. responses.LLM exposes the Responses
    # API param surface: temperature (not top_p — Responses rejects setting both),
    # max_output_tokens, service_tier, verbosity, tool_choice and a Reasoning object for
    # reasoning_effort. These match src/api/models/api_schemas.py::AssistantLLMConfig.
    temperature = llm_config.get("temperature")
    if temperature is not None:
        kwargs["temperature"] = temperature
    max_output_tokens = llm_config.get("max_output_tokens")
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    service_tier = llm_config.get("service_tier")
    if service_tier:
        kwargs["service_tier"] = service_tier
    verbosity = llm_config.get("verbosity")
    if verbosity:
        kwargs["verbosity"] = verbosity
    tool_choice = llm_config.get("tool_choice")
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    parallel_tool_calls = llm_config.get("parallel_tool_calls")
    if parallel_tool_calls is not None:
        kwargs["parallel_tool_calls"] = parallel_tool_calls
    reasoning_effort = llm_config.get("reasoning_effort")
    if reasoning_effort:
        kwargs["reasoning"] = Reasoning(effort=reasoning_effort)

    return openai.responses.LLM(**kwargs)
