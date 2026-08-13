"""Which cascade LLM knobs each OpenAI model actually accepts.

One table, two readers: the API schema validator (`api_schemas/config/llm_config.py`)
rejects an impossible pairing at create/update time, and the runtime factory
(`agents/llm/factory.py`) drops one that a stored config still holds. It lives in
`core/agents/` rather than beside either of them because the two live in different
deployments — the control image has no `livekit-agents`, the agent image has no FastAPI —
and this module must import cleanly into both. Keep it dependency-free.

Membership is spelled out per model instead of matched by prefix. The families do not
follow the prefix: `gpt-5.2-chat-latest` starts with "gpt-5" but is a chat model that
rejects `reasoning.effort`, and a prefix test silently sent it anyway. The cost of a wrong
answer here is the whole call: OpenAI replies 400, the Responses plugin raises a
non-retryable APIStatusError inside `_llm_inference_task`, and it does so on every turn —
the assistant answers, greets nobody and never speaks.
"""

# What cascade runs when the assistant sets no model. Lives here so the API validator can
# check the knobs against the model the call will actually use, not against None.
DEFAULT_CASCADE_MODEL = "gpt-4.1"

# Reasoning models: they take `reasoning.effort` and reject `temperature` and the other
# sampling knobs. https://docs.livekit.io/reference/agents/inference-llm-parameters/
REASONING_MODELS = frozenset(
    {
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5.1",
        "gpt-5.2",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5.5",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    }
)

# Non-reasoning chat models: temperature yes, reasoning.effort no. The `*-chat-latest`
# aliases track a gpt-5.x *chat* snapshot, so they belong here and not above — but they are
# still the gpt-5 generation for `text.verbosity` (see GPT5_GENERATION).
# gpt-oss-120b is the open-weight model; it is served through third-party providers rather
# than the OpenAI platform, so it gets the conservative (chat) knob set.
CHAT_MODELS = frozenset(
    {
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5.1-chat-latest",
        "gpt-5.2-chat-latest",
        "gpt-5.3-chat-latest",
        "chat-latest",
        "gpt-oss-120b",
    }
)

# Everything cascade mode will run. The API allowlist (OPENAI_CASCADE_MODELS) is this set.
CASCADE_MODELS = REASONING_MODELS | CHAT_MODELS

# `text.verbosity` is a gpt-5 generation parameter, which includes that generation's chat
# aliases. Older models reject it.
GPT5_GENERATION = REASONING_MODELS | frozenset(
    {"gpt-5.1-chat-latest", "gpt-5.2-chat-latest", "gpt-5.3-chat-latest", "chat-latest"}
)

# These reasoning models reject `reasoning.effort` once function tools are attached —
# mirrors livekit.agents.inference.llm._REASONING_EFFORT_TOOL_INCOMPATIBLE_PREFIXES, which
# the Responses plugin never applies (it calls drop_unsupported_params without `tools`, and
# the filter matches the key "reasoning_effort" while the Responses payload key is
# "reasoning"). So the check has to happen on our side. See
# agents/llm/factory.py::create_llm, which also has to undo the plugin's *own* injected
# default for these models.
REASONING_TOOL_INCOMPATIBLE = frozenset({"gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"})

# Models where openai.responses.LLM inserts a Reasoning object on its own when the caller
# passes none (plugins/openai/responses/llm.py, `_supports_reasoning_effort`). Filtering our
# own kwargs is not enough for these — the knob arrives even from an empty config.
PLUGIN_INJECTS_REASONING = frozenset(
    {"gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini"}
)


# ── Realtime models (pipeline + realtime modes) ──────────────────────────────────────
# Two generations behind one API. The `gpt-realtime*` line is the GA Realtime API; the
# `gpt-4o-*realtime-preview` pair is the older beta, still allowlisted because assistants
# run on it. `session.truncation` (retention_ratio + token_limits) arrived with the GA line
# and is not part of the beta session shape, so it is sent only to the models below —
# an unknown session field is answered with an error event, and the session never settles.
# Semantic VAD predates the split and goes to both.
REALTIME_TRUNCATION_MODELS = frozenset(
    {"gpt-realtime", "gpt-realtime-1.5", "gpt-realtime-2", "gpt-realtime-2025-08-28", "gpt-realtime-mini"}
)


def realtime_supports_truncation(model: str) -> bool:
    """True when this realtime model takes the GA `session.truncation` field."""
    return model in REALTIME_TRUNCATION_MODELS


def unsupported_knob_reason(model: str, knob: str, *, has_tools: bool = False) -> str | None:
    """Why this generation knob cannot go to this model, or None when the model reads it.

    `has_tools` is whether the session attaches function tools; it changes the answer for
    `reasoning_effort` on the models in REASONING_TOOL_INCOMPATIBLE. The API validator
    cannot know it (tools are attached per session, not per config) and passes False, so
    that particular pairing is caught at call time only.

    An unknown model — one outside CASCADE_MODELS, i.e. a row written before the allowlist
    or by a direct DB edit — gets None for every knob. The knobs are forwarded as-is rather
    than guessed at; guessing is what the prefix test used to do.
    """
    if model not in CASCADE_MODELS:
        return None

    if knob == "temperature" and model in REASONING_MODELS:
        return f"{model} is a reasoning model and rejects temperature — set reasoning_effort instead"

    if knob == "reasoning_effort":
        if model not in REASONING_MODELS:
            return f"reasoning.effort is a reasoning-model parameter and {model} rejects it"
        if has_tools and model in REASONING_TOOL_INCOMPATIBLE:
            return f"{model} rejects reasoning.effort when function tools are attached"

    if knob == "verbosity" and model not in GPT5_GENERATION:
        return f"text.verbosity is a gpt-5 parameter and {model} rejects it"

    return None
