import logging
import time
from typing import Any, Optional

import httpx

from src.core.db.db_schemas import ActivityLog, InboundContextStrategy

logger = logging.getLogger(__name__)


def _key_paths(data: Any, prefix: str = "", limit: int = 200) -> list[str]:
    """Flatten a JSON object into sorted dotted key paths, values discarded.

    The context payload holds caller PII (names, phone numbers), so the activity
    log records only the shape. A list is summarized as ``key[]`` plus the paths
    of its first element — enough to tell whether a placeholder will resolve,
    without one path per row.
    """
    paths: list[str] = []

    def walk(node: Any, path: str) -> None:
        if len(paths) >= limit:
            return
        if isinstance(node, dict):
            if not node:
                paths.append(path or "{}")
                return
            for key in sorted(node.keys()):
                walk(node[key], f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            paths.append(f"{path}[]")
            if node:
                walk(node[0], f"{path}[0]")
        else:
            paths.append(path)

    walk(data, prefix)
    return paths[:limit]


async def _log_lookup(
    *,
    user_email: str,
    assistant_id: str,
    room_name: str,
    request_data: dict[str, Any],
    status: str,
    latency_ms: int,
    message: str,
    response_data: Optional[dict[str, Any]] = None,
) -> None:
    """Write a single inbound context lookup activity log."""
    try:
        await ActivityLog(
            user_email=user_email,
            log_type="inbound_context_lookup",
            assistant_id=assistant_id,
            room_name=room_name,
            status=status,
            request_data=request_data,
            response_data=response_data,
            latency_ms=latency_ms,
            message=message,
        ).insert()
    except Exception as log_err:
        logger.warning(f"Failed to write inbound context lookup log: {log_err}")


async def log_missing_strategy(
    *,
    user_email: str,
    assistant_id: str,
    room_name: str,
    strategy_id: str,
) -> None:
    """Record an inbound call whose configured strategy was missing or inactive.

    Same activity-log stream as a failed lookup, so a strategy that was deleted
    out from under a live inbound number is visible rather than silent.
    """
    await _log_lookup(
        user_email=user_email,
        assistant_id=assistant_id,
        room_name=room_name,
        request_data={"strategy_id": strategy_id},
        status="error",
        latency_ms=0,
        message=(
            f"Inbound context strategy '{strategy_id}' not found or inactive; "
            "continuing with default prompt"
        ),
    )


async def resolve_inbound_context(
    *,
    strategy: InboundContextStrategy,
    assistant_id: str,
    assistant_name: str,
    user_email: str,
    room_name: str,
    job_metadata: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    Fetch caller-specific inbound context from a customer webhook.

    The whole JSON response object is the context payload — its own shape is the
    placeholder path, the same rule outbound `metadata` already follows. A flat
    ``{"name": "x"}`` renders ``{{name}}``; a nested ``{"context": {"name": "x"}}``
    renders ``{{context.name}}``. No key is treated as an envelope.

    Returns the response dictionary on success, or None when the lookup should
    gracefully fall back to the assistant's default prompt behavior.
    """
    payload = {
        "assistant_id": assistant_id,
        "assistant_name": assistant_name,
        "room_name": room_name,
        "strategy_id": strategy.strategy_id,
        "strategy_name": strategy.strategy_name,
        "strategy_type": strategy.strategy_type,
        "call_type": job_metadata.get("call_type"),
        "service": job_metadata.get("service"),
        "inbound_id": job_metadata.get("inbound_id"),
        "caller_number": job_metadata.get("caller_number"),
        "inbound_number": job_metadata.get("inbound_number"),
    }
    config = strategy.strategy_config or {}
    url = config.get("url")
    request_data = {
        "strategy_id": strategy.strategy_id,
        "strategy_type": strategy.strategy_type,
        "url": url,
        "payload": payload,
    }
    start_ms = time.monotonic()

    if strategy.strategy_type != "webhook":
        message = (
            f"Unsupported inbound context strategy type '{strategy.strategy_type}'; "
            "continuing with default prompt"
        )
        logger.warning(f"{message} (strategy {strategy.strategy_id})")
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=0,
            message=message,
        )
        return None

    if not url:
        message = (
            f"Inbound context strategy {strategy.strategy_id} is missing a webhook URL; "
            "continuing with default prompt"
        )
        logger.warning(message)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=0,
            message=message,
        )
        return None

    # Config comes straight from Mongo, so it can hold anything a legacy or
    # hand-edited document left behind — a null headers map used to TypeError
    # here and take the whole call down with it.
    raw_timeout = config.get("timeout_seconds") or 10.0
    try:
        timeout_seconds = min(max(float(raw_timeout), 0.5), 10.0)
    except (TypeError, ValueError):
        timeout_seconds = 10.0
    headers = {"Content-Type": "application/json", **(config.get("headers") or {})}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.monotonic() - start_ms) * 1000)

        # A list, string, or number cannot be merged into the render data.
        if not isinstance(data, dict):
            message = (
                "Inbound context lookup did not return a JSON object; "
                "continuing with default prompt"
            )
            await _log_lookup(
                user_email=user_email,
                assistant_id=assistant_id,
                room_name=room_name,
                request_data=request_data,
                status="error",
                latency_ms=latency_ms,
                message=message,
                response_data={"response_type": type(data).__name__},
            )
            logger.warning(message)
            return None

        key_paths = _key_paths(data)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="success",
            latency_ms=latency_ms,
            message="Inbound context lookup completed successfully",
            response_data={
                "context_key_paths": key_paths,
                "context_size": len(key_paths),
            },
        )
        return data

    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        message = (
            f"Inbound context lookup timed out after {timeout_seconds}s; "
            "continuing with default prompt"
        )
        logger.warning(message)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=latency_ms,
            message=message,
        )
    except httpx.HTTPStatusError as exc:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        status_code = exc.response.status_code
        message = (
            f"Inbound context lookup returned HTTP {status_code}; "
            "continuing with default prompt"
        )
        logger.warning(message)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=latency_ms,
            message=message,
            response_data={"status_code": status_code},
        )
    except ValueError as exc:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        message = (
            f"Inbound context lookup returned invalid JSON: {exc}; "
            "continuing with default prompt"
        )
        logger.warning(message)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=latency_ms,
            message=message,
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start_ms) * 1000)
        message = (
            f"Inbound context lookup failed: {exc}; "
            "continuing with default prompt"
        )
        logger.warning(message)
        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="error",
            latency_ms=latency_ms,
            message=message,
        )

    return None
