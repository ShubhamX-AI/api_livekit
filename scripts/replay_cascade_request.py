"""Replay a cascade assistant's LLM request over HTTPS to see why OpenAI refused it.

Read-only. Reads one assistant (and its tools) from MongoDB, sends one short request, writes
nothing anywhere.

## Why this exists

When a cascade call fails, the worker log says exactly this and nothing more:

    livekit.agents._exceptions.APIStatusError: message='There was an issue with your request.
    Please check your inputs and try again', status_code=-1, retryable=False

`status_code=-1` is the giveaway: that is not an HTTP reply. The Responses plugin talks over a
WebSocket, and a rejection arrives as an error frame with no detail — no parameter name, no
model name, no status. The error is raised per turn and is non-retryable, so the caller gets a
connected line and silence for the whole call.

Sent over plain HTTPS instead, the same request sometimes answers with the detail:

    {"error": {"message": "Unsupported value: 'reasoning.effort' does not support 'none' with
    this model.", "param": "reasoning.effort", ...}}

and sometimes does not. Measured against a real assistant: `gpt-4.1-nano` carrying
`service_tier: "flex"` — a tier that model cannot use — answers HTTP 400 with the *same*
detail-free "check your inputs" text and no `param` at all.

So this script does both. It rebuilds the exact payload the runtime builds
(`model_support.payload`, plus the exact tool schemas from `model_support.tool_schema`), POSTs
it, and prints whatever OpenAI says — then, **when OpenAI names no parameter, it bisects
automatically**, re-sending with one knob removed at a time until it can name the offender.
Telling someone to re-run the command they just ran is not a diagnosis.

## Usage

    uv run python scripts/replay_cascade_request.py <assistant_id>
    uv run python scripts/replay_cascade_request.py <assistant_id> --show-payload
    uv run python scripts/replay_cascade_request.py <assistant_id> --bisect

`--bisect` forces the knob-by-knob pass even when OpenAI *did* name a parameter — worth it when
a second offending knob may be hiding behind the first.

Exit code 0 when OpenAI accepts the request, 1 when it refuses. The assistant's own API key is
used when it has one, otherwise `OPENAI_API_KEY`. The key is never printed.
"""

import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.model_support.capabilities import DEFAULT_CASCADE_MODEL  # noqa: E402
from src.core.model_support.openai_live import RESPONSES_URL  # noqa: E402
from src.core.model_support.payload import build_responses_payload  # noqa: E402
from src.core.model_support.tool_schema import (  # noqa: E402
    END_CALL_TOOL_SCHEMA,
    ToolNameTooLong,
    build_tool_schema,
)

# The knobs worth removing one at a time. `max_output_tokens` is not among them: the replay
# sets its own small cap, so the stored value never reaches the wire here.
_BISECTABLE_KNOBS = (
    "reasoning_effort",
    "service_tier",
    "verbosity",
    "temperature",
    "tool_choice",
    "parallel_tool_calls",
)


class Param:
    """A tool parameter, shaped like the Beanie `ToolParameter` build_tool_schema expects."""

    def __init__(self, raw: dict):
        self.name = raw.get("name")
        self.type = raw.get("type")
        self.description = raw.get("description")
        self.enum = raw.get("enum")
        self.required = raw.get("required", False)


async def load_assistant(db, assistant_id: str) -> dict:
    doc = await db["assistants"].find_one({"assistant_id": assistant_id})
    if not doc:
        raise SystemExit(f"No assistant with assistant_id {assistant_id!r}.")
    return doc


async def load_tool_schemas(db, assistant: dict, *, strict_schemas: bool) -> list[dict]:
    """The tool schemas this assistant's calls actually send, built the runtime's way."""
    schemas = []
    tool_ids = assistant.get("tool_ids") or []
    if tool_ids:
        cursor = db["tools"].find({"tool_id": {"$in": tool_ids}, "tool_is_active": True})
        async for tool_doc in cursor:
            params = [Param(p) for p in (tool_doc.get("tool_parameters") or [])]
            try:
                schema, relaxed_by = build_tool_schema(
                    tool_doc.get("tool_name"),
                    tool_doc.get("tool_description"),
                    params,
                    strict_schemas=strict_schemas,
                )
            except ToolNameTooLong as e:
                print(f"  ! skipping tool {tool_doc.get('tool_name')!r}: {e}")
                continue
            if relaxed_by and strict_schemas:
                print(
                    f"  tool {schema['name']!r}: strict off ({', '.join(relaxed_by)})"
                )
            schemas.append(schema)

    if assistant.get("assistant_end_call_enabled"):
        schemas.append(END_CALL_TOOL_SCHEMA)
    return schemas


async def send(payload: dict, api_key: str) -> tuple[int, dict | str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        response = await client.post(
            RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, response.text[:500]


def describe_error(body) -> tuple[str, bool]:
    """Return `(message, actionable)`. `actionable` means OpenAI named the parameter.

    It frequently does not — `gpt-4.1-nano` with a `service_tier` it cannot use answers with
    the same "There was an issue with your request. Please check your inputs and try again" as
    the WebSocket does. That is what the automatic bisect below exists for.
    """
    if isinstance(body, dict):
        error = body.get("error") or {}
        message = error.get("message")
        if message:
            param = error.get("param")
            if param:
                return f"{message}  [param: {param}]", True
            return str(message), False
        return json.dumps(body)[:500], False
    return str(body)[:500], False


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(
            "Usage: uv run python scripts/replay_cascade_request.py <assistant_id> "
            "[--show-payload] [--bisect]"
        )
    assistant_id = args[0]
    show_payload = "--show-payload" in sys.argv
    bisect = "--bisect" in sys.argv

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    assistant = await load_assistant(db, assistant_id)

    mode = assistant.get("assistant_mode")
    llm_config = assistant.get("assistant_llm_config") or {}
    model = llm_config.get("model") or DEFAULT_CASCADE_MODEL
    api_key = llm_config.get("api_key") or settings.OPENAI_API_KEY
    if not api_key:
        raise SystemExit("No OpenAI key on the assistant and OPENAI_API_KEY is not set.")

    print(f"assistant : {assistant_id}  ({assistant.get('assistant_name')!r})")
    print(f"mode      : {mode}")
    print(f"model     : {model}")
    print(f"key       : {'per-assistant' if llm_config.get('api_key') else 'system'}")
    knobs = {k: v for k, v in llm_config.items() if k not in ("api_key", "model", "provider")}
    print(f"knobs     : {knobs or 'defaults'}")

    if mode != "cascade":
        print(
            f"\nNote: this assistant is in {mode!r} mode, which drives the Realtime API, not "
            "the Responses API. The replay below still tells you whether the model and knobs "
            "are valid for Responses, but a realtime session's own failures will not show up "
            "here."
        )

    tools = await load_tool_schemas(db, assistant, strict_schemas=mode == "cascade")
    print(f"tools     : {len(tools)} ({', '.join(t['name'] for t in tools) or 'none'})")

    payload = build_responses_payload(
        model,
        llm_config,
        tools=tools,
        instructions=assistant.get("assistant_prompt"),
        input_text="ping",
        max_output_tokens=16,
        store=False,
    )
    if show_payload:
        print("\npayload sent (api key is in the header, not here):")
        print(json.dumps(payload, indent=2, sort_keys=True))

    status, body = await send(payload, api_key)
    if status < 400:
        print(f"\nOpenAI accepted the request (HTTP {status}).")
        print(
            "So the model and knobs are fine. If calls still fail, the difference is "
            "elsewhere: check the STT/TTS stage, or a knob the plugin injects by itself "
            "(see create_llm's handling of reasoning effort with tools)."
        )
        raise SystemExit(0)

    message, actionable = describe_error(body)
    print(f"\nOpenAI refused the request (HTTP {status}):")
    print(f"  {message}")

    # A refusal that names no parameter is unactionable on its own — the WebSocket text and the
    # HTTPS text can be the identical "check your inputs", measured against a real assistant. So
    # bisect without being asked: telling someone to re-run the command they just ran is not a
    # diagnosis. Explicit --bisect still forces it when OpenAI *did* name a parameter, because
    # a second offending knob can hide behind the first.
    if actionable and not bisect:
        print("\nOpenAI named the parameter above. Re-run with --bisect to check for a second.")
        raise SystemExit(1)

    candidates = [knob for knob in _BISECTABLE_KNOBS if llm_config.get(knob) is not None]
    if not candidates:
        print(
            "\nNothing to bisect: this config sets none of the optional knobs, so the request "
            "shape itself is the problem — most likely a function tool's schema. Re-run with "
            "--show-payload and read the `tools` array."
        )
        raise SystemExit(1)

    if not actionable:
        print("\nNo parameter named, so bisecting automatically — one knob removed at a time:")
    else:
        print("\nBisecting — removing one knob at a time:")

    culprits = []
    for knob in candidates:
        reduced = {k: v for k, v in llm_config.items() if k != knob}
        reduced_payload = build_responses_payload(
            model,
            reduced,
            tools=tools,
            instructions=assistant.get("assistant_prompt"),
            input_text="ping",
            max_output_tokens=16,
            store=False,
        )
        reduced_status, _ = await send(reduced_payload, api_key)
        verdict = "ACCEPTED without it" if reduced_status < 400 else "still refused"
        print(f"  without {knob}={llm_config[knob]!r}: {verdict}")
        if reduced_status < 400:
            culprits.append(knob)

    if culprits:
        print(f"\nOffending knob(s): {', '.join(culprits)}")
        print("Clear them with a PATCH sending each as null:")
        clear_body = json.dumps({"assistant_llm_config": {knob: None for knob in culprits}})
        print(f"  PATCH /assistant/update/{assistant_id}")
        print(f"  {clear_body}")
    else:
        print(
            "\nNo single knob explains it — so either two of them only fail together, or the "
            "problem is elsewhere. Remaining suspects, in order: a tool schema (re-run with "
            "--show-payload and read the `tools` array), the model id itself (run "
            "scripts/check_model_allowlist.py), or the instructions being too long."
        )
    raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
