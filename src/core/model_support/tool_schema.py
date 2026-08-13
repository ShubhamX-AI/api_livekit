"""One tool document to one OpenAI function schema — and when `strict` has to come off.

Extracted from `agents/tool_builder.py` so three callers can share exactly one answer:

- the runtime, which attaches the schema to the session (`tool_builder`);
- the API, which has to reject a tool combination that would break every LLM turn;
- `scripts/replay_cascade_request.py`, which replays the real request to get OpenAI's real
  error message instead of the generic WebSocket frame.

An approximation here would defeat the point of the last two: the whole class of bug being
guarded against is a request body that looks right and is not.

Dependency-free, like the rest of `model_support`. It takes plain values rather than a Beanie
`Tool` document so the control image (no `livekit-agents`) and the agent image (no FastAPI)
can both call it.
"""

# OpenAI rejects a function whose name is longer than this. The API accepts tool names up
# to 100 characters (api_schemas/tools.py), so the two limits can disagree.
MAX_TOOL_NAME_LEN = 64

# The built-in end_call tool, exactly as the session attaches it (agents/session.py). No
# parameters, so it is strict-valid as it stands.
#
# It lives here because three places need the same bytes: the config probe, the replay script,
# and anything else that has to predict what OpenAI will see. Its mere presence changes what
# OpenAI accepts — `tool_choice: "required"` becomes legal, and `gpt-5.2`/`gpt-5.4*` start
# rejecting `reasoning.effort` — so a probe that omits it, or spells it differently, gives the
# wrong answer.
END_CALL_TOOL_SCHEMA = {
    "type": "function",
    "name": "end_call",
    "description": "End the call after saying goodbye.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

# Types this builder cannot describe completely: the Tool document has no nested schema for
# an object's properties or an array's items, and strict mode requires both.
UNDESCRIBABLE_TYPES = frozenset({"object", "array"})


class ToolNameTooLong(ValueError):
    """The tool name exceeds OpenAI's function-name limit.

    Its own type so callers can skip the one offending tool instead of losing the whole
    request — OpenAI rejects the entire call, taking every other tool with it.
    """


def build_tool_schema(
    name: str, description: str, parameters, *, strict_schemas: bool = False
) -> tuple[dict, list[str]]:
    """Return `(schema, relaxed_by)` for one tool.

    `parameters` is any iterable of objects with `.name`, `.type`, `.description`, `.enum` and
    `.required` — a Beanie `ToolParameter`, or anything shaped like one.

    `relaxed_by` lists the reasons `strict` was switched off, empty when the schema is
    strict-valid. Callers log it; nothing else depends on it.

    Strict mode is the part that needs care, and it is cascade-only (`strict_schemas`).
    The Responses API defaults function tools to `strict`, and a strict schema must list
    *every* property in `required` and must fully describe every object and array. A schema
    that breaks either rule is not ignored — the API answers 400, the plugin raises it
    non-retryable on every LLM turn, and the assistant answers the call and never speaks.
    So: leave the tool strict when this document happens to describe one (all parameters
    required, no object/array), and turn strict off explicitly when it does not, rather than
    emitting a strict schema that is invalid.

    The Realtime API behind pipeline/realtime mode has no `strict` concept at all, and an
    unknown key in a session tool is an error rather than a shrug — so nothing is emitted
    there. Same schema otherwise: one tool document, two wire formats.
    """
    properties: dict = {}
    required: list[str] = []
    relaxed_by: list[str] = []

    for param in parameters or []:
        prop_def = {"type": param.type}

        if param.description:
            prop_def["description"] = param.description

        if param.enum:
            prop_def["enum"] = param.enum

        properties[param.name] = prop_def

        if param.required:
            required.append(param.name)
        else:
            relaxed_by.append(f"{param.name} is optional")

        if param.type in UNDESCRIBABLE_TYPES:
            relaxed_by.append(f"{param.name} is a bare {param.type}")

    if len(name) > MAX_TOOL_NAME_LEN:
        raise ToolNameTooLong(
            f"tool name is {len(name)} characters; OpenAI allows "
            f"{MAX_TOOL_NAME_LEN}. Rename the tool."
        )

    schema = {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }

    if relaxed_by and strict_schemas:
        schema["strict"] = False

    return schema, relaxed_by
