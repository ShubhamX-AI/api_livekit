"""Factory for the conversational LLM used in cascade mode.

Only cascade mode needs this. The `pipeline` and `realtime` modes build a
`RealtimeModel` inline in session.py, because their LLM also owns STT (and, in
realtime, TTS) — there is nothing to factor out. Cascade is the only mode where
the LLM is a standalone stage.
"""

from livekit.agents.types import NOT_GIVEN
from livekit.plugins import openai
from openai.types import Reasoning

from src.core.agents.llm_capabilities import (
    DEFAULT_CASCADE_MODEL,
    PLUGIN_INJECTS_REASONING,
    REASONING_TOOL_INCOMPATIBLE,
    unsupported_knob_reason,
)
from src.core.config import settings
from src.core.logger import logger

# Kept as a plain string default, not a Literal. OpenAI ships models monthly and a
# Literal would mean a deploy per model; the supported set is documented instead
# (docs/architecture/cascade-pipeline.md). It lives in llm_capabilities so the API
# validator can check the knobs against the model the call will actually use.
DEFAULT_MODEL = DEFAULT_CASCADE_MODEL


def create_llm(assistant, *, has_tools: bool = False):
    """Build a non-realtime LLM from the assistant's LLM config. Returns None on error.

    `has_tools` is whether the session attaches function tools (DB-backed tools or the
    built-in end_call). Not cosmetic: two of the gpt-5 models reject `reasoning.effort`
    outright once tools are present, and the plugin sets that effort by itself.
    """
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
    model = llm_config.get("model") or DEFAULT_MODEL
    kwargs: dict = {
        "model": model,
        "api_key": api_key,
    }

    def keep(knob: str, value) -> bool:
        """True when this model reads the knob; logs what it dropped when it does not.

        A knob the model does not read is not ignored on OpenAI's side: the Responses API
        answers 400, the plugin raises it as a non-retryable APIStatusError inside
        _llm_inference_task, and it does so on every turn — the assistant answers the call,
        greets nobody and never speaks. A stale knob is easy to arrive at honestly: set
        reasoning_effort on gpt-5, later switch the assistant to gpt-4.1, and the effort
        stays in the stored config. Dropping it here means the model the operator picked is
        the only thing that decides which knobs are sent.
        """
        reason = unsupported_knob_reason(model, knob, has_tools=has_tools)
        if reason is None:
            return True
        logger.warning(
            f"Dropping {knob}={value!r} for cascade assistant {assistant_id}: {reason}. "
            f"Sending it to {model} fails the LLM turn, so the call would connect and stay "
            "silent. Update the assistant to clear the stale value."
        )
        return False

    # Generation knobs from assistant_llm_config — forwarded only when explicitly set in
    # config, so omitted knobs keep the SDK defaults. responses.LLM exposes the Responses
    # API param surface: temperature (not top_p — Responses rejects setting both),
    # max_output_tokens, service_tier, verbosity, tool_choice and a Reasoning object for
    # reasoning_effort. These match src/api/models/api_schemas.py::AssistantLLMConfig.
    #
    # Three of them are model-gated, and the stored config can hold a value the current
    # model rejects — which model reads which is src/core/agents/llm_capabilities.py.
    temperature = llm_config.get("temperature")
    if temperature is not None and keep("temperature", temperature):
        kwargs["temperature"] = temperature
    max_output_tokens = llm_config.get("max_output_tokens")
    if max_output_tokens is not None:
        kwargs["max_output_tokens"] = max_output_tokens
    service_tier = llm_config.get("service_tier")
    if service_tier:
        kwargs["service_tier"] = service_tier
    verbosity = llm_config.get("verbosity")
    if verbosity and keep("verbosity", verbosity):
        kwargs["verbosity"] = verbosity
    tool_choice = llm_config.get("tool_choice")
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    parallel_tool_calls = llm_config.get("parallel_tool_calls")
    if parallel_tool_calls is not None:
        kwargs["parallel_tool_calls"] = parallel_tool_calls
    reasoning_effort = llm_config.get("reasoning_effort")
    if reasoning_effort and keep("reasoning_effort", reasoning_effort):
        kwargs["reasoning"] = Reasoning(effort=reasoning_effort)

    llm = openai.responses.LLM(**kwargs)

    # Filtering our own kwargs is not enough. openai.responses.LLM.__init__ inserts a
    # Reasoning object of its own for the gpt-5 models it believes support one, so the knob
    # reaches OpenAI even from an assistant with an empty config. On gpt-5.2 and gpt-5.4*
    # that is a 400 as soon as function tools are attached, and the SDK's own guard for it
    # never fires here: the Responses plugin calls drop_unsupported_params without `tools`,
    # and that filter matches the key "reasoning_effort" while the Responses payload key is
    # "reasoning". Clearing the option after construction is the narrowest counter, and it
    # can be deleted once the plugin fixes either half. Covered by tests/test_cascade_config.
    if has_tools and "reasoning" not in kwargs and model in REASONING_TOOL_INCOMPATIBLE:
        if model in PLUGIN_INJECTS_REASONING:
            logger.info(
                f"Cascade assistant {assistant_id}: clearing the reasoning effort the OpenAI "
                f"plugin injects for {model} — that model rejects reasoning.effort while "
                "function tools are attached."
            )
        llm._opts.reasoning = NOT_GIVEN

    # A Responses 400 is about the request shape, and over the WebSocket the error frame
    # carries no detail ("There was an issue with your request. Please check your inputs
    # and try again"), so the knobs that produced it have to be in our own log. Never the
    # API key.
    logger.info(
        "Cascade LLM built | assistant=%s | model=%s | has_tools=%s | knobs=%s",
        assistant_id,
        model,
        has_tools,
        {k: v for k, v in kwargs.items() if k not in ("api_key", "model")} or "defaults",
    )
    return llm
