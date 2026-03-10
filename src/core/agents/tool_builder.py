"""
tool_builder.py — Convert database Tool documents into LiveKit function_tool objects.

At runtime, when a session starts, this module:
1. Loads tool definitions from MongoDB by their tool_ids
2. Builds a raw JSON schema for each tool (name, description, parameters)
3. Creates an async executor function per tool (webhook or static_return)
4. Wraps everything into LiveKit function_tool objects
"""

import logging
import time
from typing import List, Any

import httpx
from livekit.agents import function_tool, RunContext

from src.core.db.db_schemas import Tool, ActivityLog

logger = logging.getLogger(__name__)


async def build_tools_from_db(tool_ids: List[str], user_email: str, room_name: str, assistant_id: str) -> list:
    """
    Load tool definitions from the database and build LiveKit function_tool objects.

    Args:
        tool_ids: List of tool_id strings to load.
        user_email: Owner email — used to attribute activity logs.
        room_name: Current call room — stored on activity logs.
        assistant_id: Current assistant — stored on activity logs.

    Returns:
        List of LiveKit FunctionTool objects ready to pass to an Agent.
    """
    if not tool_ids:
        return []

    # Fetch all active tools matching the provided IDs
    tools = await Tool.find(
        {"tool_id": {"$in": tool_ids}, "tool_is_active": True}
    ).to_list()

    if not tools:
        logger.warning(f"No active tools found for IDs: {tool_ids}")
        return []

    built_tools = []
    for tool_doc in tools:
        try:
            ft = _build_single_tool(tool_doc, user_email, room_name, assistant_id)
            built_tools.append(ft)
            logger.info(f"Built tool: {tool_doc.tool_name} ({tool_doc.tool_id})")
        except Exception as e:
            logger.error(f"Failed to build tool {tool_doc.tool_name}: {e}")

    return built_tools


def _build_single_tool(tool_doc: Tool, user_email: str, room_name: str, assistant_id: str):
    """Convert a single Tool document into a LiveKit function_tool."""

    # 1. Build the raw JSON schema
    raw_schema = _build_raw_schema(tool_doc)

    # 2. Create the executor based on execution type
    executor = _create_executor(tool_doc, user_email, room_name, assistant_id)

    # 3. Wrap into a LiveKit function_tool using raw_schema
    return function_tool(executor, raw_schema=raw_schema)


def _build_raw_schema(tool_doc: Tool) -> dict:
    """
    Build a raw function-calling schema from the Tool document.

    Produces the format expected by LiveKit/OpenAI:
    {
        "type": "function",
        "name": "tool_name",
        "description": "...",
        "parameters": { "type": "object", "properties": {...}, "required": [...] }
    }
    """
    properties = {}
    required = []

    for param in tool_doc.tool_parameters:
        prop_def = {"type": param.type}

        if param.description:
            prop_def["description"] = param.description

        if param.enum:
            prop_def["enum"] = param.enum

        properties[param.name] = prop_def

        if param.required:
            required.append(param.name)

    schema = {
        "type": "function",
        "name": tool_doc.tool_name,
        "description": tool_doc.tool_description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }

    return schema


def _create_executor(tool_doc: Tool, user_email: str, room_name: str, assistant_id: str):
    """
    Create an async executor function for the given tool.

    The executor signature must be: async def handler(raw_arguments: dict, context: RunContext)
    because we are using raw_schema mode.
    """
    execution_type = tool_doc.tool_execution_type
    config = tool_doc.tool_execution_config

    if execution_type == "webhook":
        return _create_webhook_executor(tool_doc.tool_name, config, user_email, room_name, assistant_id)
    elif execution_type == "static_return":
        return _create_static_return_executor(tool_doc.tool_name, config)
    else:
        raise ValueError(f"Unsupported execution type: {execution_type}")


async def _log_tool_call(
    user_email: str, assistant_id: str, room_name: str,
    url: str, raw_arguments: dict,
    status: str, latency_ms: int, message: str,
    response_data: dict | None = None,
) -> None:
    """Write a single tool_call activity log, swallowing any DB errors."""
    try:
        await ActivityLog(
            user_email=user_email,
            log_type="tool_call",
            assistant_id=assistant_id,
            room_name=room_name,
            status=status,
            request_data={"url": url, "arguments": raw_arguments},
            response_data=response_data,
            latency_ms=latency_ms,
            message=message,
        ).insert()
    except Exception as log_err:
        logger.warning(f"Failed to write activity log: {log_err}")


def _create_webhook_executor(tool_name: str, config: dict, user_email: str, room_name: str, assistant_id: str):
    """
    Create an executor that POSTs tool arguments to a webhook URL.

    Config format:
        {
            "url": "https://api.example.com/weather",
            "headers": {"Authorization": "Bearer ..."} ,  # optional
            "timeout": 30  # optional, seconds
        }
    """
    url = config.get("url")
    if not url:
        raise ValueError(f"Webhook tool '{tool_name}' is missing 'url' in execution_config")

    custom_headers = config.get("headers", {})
    timeout = config.get("timeout", 30)

    async def webhook_handler(raw_arguments: dict[str, object], context: RunContext) -> Any:
        logger.info(f"Tool '{tool_name}' calling webhook: {url}")
        logger.debug(f"Tool '{tool_name}' args: {raw_arguments}")

        headers = {"Content-Type": "application/json", **custom_headers}
        start_ms = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=raw_arguments, headers=headers)
                response.raise_for_status()

                # Try to parse as JSON, fall back to text
                try:
                    result = response.json()
                except Exception:
                    result = response.text

                latency = int((time.monotonic() - start_ms) * 1000)
                logger.info(f"Tool '{tool_name}' webhook returned status {response.status_code}")

                await _log_tool_call(
                    user_email, assistant_id, room_name, url, raw_arguments,
                    status="success", latency_ms=latency,
                    message=f"Tool '{tool_name}' called {url} — {response.status_code}",
                    response_data=result if isinstance(result, dict) else {"response": result},
                )

                return result

        except httpx.TimeoutException:
            latency = int((time.monotonic() - start_ms) * 1000)
            logger.error(f"Tool '{tool_name}' webhook timed out after {timeout}s")
            await _log_tool_call(
                user_email, assistant_id, room_name, url, raw_arguments,
                status="error", latency_ms=latency,
                message=f"Tool '{tool_name}' timed out after {timeout}s calling {url}",
            )
            return {"error": f"Webhook timed out after {timeout}s"}

        except httpx.HTTPStatusError as e:
            latency = int((time.monotonic() - start_ms) * 1000)
            logger.error(f"Tool '{tool_name}' webhook returned {e.response.status_code}")
            await _log_tool_call(
                user_email, assistant_id, room_name, url, raw_arguments,
                status="error", latency_ms=latency,
                message=f"Tool '{tool_name}' got HTTP {e.response.status_code} from {url}",
            )
            return {"error": f"Webhook returned status {e.response.status_code}"}

        except Exception as e:
            latency = int((time.monotonic() - start_ms) * 1000)
            logger.error(f"Tool '{tool_name}' webhook failed: {e}")
            await _log_tool_call(
                user_email, assistant_id, room_name, url, raw_arguments,
                status="error", latency_ms=latency,
                message=f"Tool '{tool_name}' failed: {str(e)}",
            )
            return {"error": f"Webhook call failed: {str(e)}"}

    return webhook_handler


def _create_static_return_executor(tool_name: str, config: dict):
    """
    Create an executor that returns a pre-configured static value.

    Config format:
        {
            "value": {"weather": "sunny", "temperature_f": 70}
        }
    """
    static_value = config.get("value")
    if static_value is None:
        raise ValueError(f"Static return tool '{tool_name}' is missing 'value' in execution_config")

    async def static_handler(raw_arguments: dict[str, object], context: RunContext) -> Any:
        logger.info(f"Tool '{tool_name}' returning static value")
        return static_value

    return static_handler
