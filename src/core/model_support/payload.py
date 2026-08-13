"""The Responses request body the cascade runtime will actually send.

Two callers need this and both need it to be *exact*, not close:

- `scripts/replay_cascade_request.py` replays it over plain HTTPS to read OpenAI's real error
  message. Over the WebSocket the plugin uses, a rejection arrives as an error frame with no
  detail at all — `status_code=-1, message='There was an issue with your request. Please
  check your inputs and try again'` — so the only way to find out *which* input is to send
  the same body somewhere that answers properly.
- the create/update probe sends it once to find out whether this key, this model and these
  knobs work together, before the combination is stored.

An approximation would be worse than nothing: it would clear a config that then fails on a
call, or reject one that would have worked.

Mirrored from `livekit/plugins/openai/responses/llm.py` (`LLM.__init__` and `LLM.chat`) and
`livekit/agents/inference/llm.py::drop_unsupported_params` in livekit-agents 1.6.x. Two
mappings there are easy to get wrong and are the reason this module exists rather than a dict
comprehension at each call site:

- `reasoning_effort` is not a top-level field. It goes to `reasoning: {effort: ...}`.
- `verbosity` is not a top-level field either. It goes to `text: {verbosity: ...}`.

Keep this in step with the plugin on every `livekit-agents` bump. `tests/test_payload.py`
asserts the shape; nothing can detect a *semantic* drift but a read of the plugin diff.
"""

# Prefixes whose models drop the sampling parameters, straight from
# `livekit.agents.inference.llm._UNSUPPORTED_PARAMS`. The plugin strips these before sending,
# so a payload that includes them is not what the runtime would send — and would be rejected
# by OpenAI here while working fine in a real call.
_SAMPLING_STRIPPED_PREFIXES = ("o1", "o3", "o4", "gpt-5")

_SAMPLING_PARAMS = frozenset(
    {
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "top_logprobs",
        "n",
    }
)


def strips_sampling_params(model: str) -> bool:
    """True when the SDK removes `temperature` and friends before sending for this model.

    Worth knowing beyond the payload: a knob the SDK silently strips is a config field that
    does nothing, which is its own kind of bug — the operator sets a temperature, the API
    stores it, `GET /assistant/details` shows it, and no request ever carries it.
    """
    return model.startswith(_SAMPLING_STRIPPED_PREFIXES)


def build_responses_payload(
    model: str,
    llm_config: dict | None,
    *,
    tools: list[dict] | None = None,
    instructions: str | None = None,
    input_text: str = "ping",
    max_output_tokens: int | None = None,
    store: bool = False,
) -> dict:
    """Build the request body for `POST /v1/responses`.

    `llm_config` is the assistant's `assistant_llm_config` dict. Only the generation knobs are
    read; `provider`, `model` and `api_key` are handled by the caller.

    Defaults suit a probe (one short turn, nothing stored). Pass `max_output_tokens=None` to
    take the value from the config instead, which is what a replay of a real turn wants.

    `tools` are already-built OpenAI function schemas — see `tool_schema.build_tool_schema`.
    When there are none, `tool_choice` and `parallel_tool_calls` are left out entirely: both
    are meaningless without tools, and `tool_choice: "required"` with an empty list is a 400
    on every turn.
    """
    config = llm_config or {}
    payload: dict = {
        "model": model,
        "input": input_text,
        "store": store,
    }

    if instructions:
        payload["instructions"] = instructions

    resolved_max_tokens = (
        max_output_tokens if max_output_tokens is not None else config.get("max_output_tokens")
    )
    if resolved_max_tokens is not None:
        payload["max_output_tokens"] = resolved_max_tokens

    temperature = config.get("temperature")
    if temperature is not None and not strips_sampling_params(model):
        payload["temperature"] = temperature

    if config.get("service_tier"):
        payload["service_tier"] = config["service_tier"]

    if config.get("verbosity"):
        payload["text"] = {"verbosity": config["verbosity"]}

    if config.get("reasoning_effort"):
        payload["reasoning"] = {"effort": config["reasoning_effort"]}

    if tools:
        payload["tools"] = tools
        if config.get("tool_choice"):
            payload["tool_choice"] = config["tool_choice"]
        if config.get("parallel_tool_calls") is not None:
            payload["parallel_tool_calls"] = config["parallel_tool_calls"]

    return payload


def gated_knob_signature(model: str, llm_config: dict | None, *, has_tools: bool) -> str:
    """A stable cache key for "this model with these knobs", ignoring anything inert.

    The probe result depends on the model, the knobs that reach OpenAI and whether tools are
    attached — not on the prompt, the key's other assistants, or a knob the SDK strips. Two
    assistants with the same combination should cost one probe between them.
    """
    config = llm_config or {}
    parts = [model, f"tools={int(bool(has_tools))}"]
    for knob in (
        "temperature",
        "max_output_tokens",
        "reasoning_effort",
        "service_tier",
        "verbosity",
        "tool_choice",
        "parallel_tool_calls",
    ):
        value = config.get(knob)
        if value is None:
            continue
        if knob == "temperature" and strips_sampling_params(model):
            continue
        if knob in ("tool_choice", "parallel_tool_calls") and not has_tools:
            continue
        parts.append(f"{knob}={value}")
    return "|".join(parts)
