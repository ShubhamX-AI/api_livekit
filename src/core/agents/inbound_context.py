import logging
import time
from typing import Any, Optional

import httpx

from src.core.db.db_schemas import ActivityLog, InboundContextStrategy

logger = logging.getLogger(__name__)


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

    Returns a context dictionary on success, or None when the lookup should
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
    if strategy.strategy_type != "webhook":
        logger.warning(
            f"Unsupported inbound context strategy type '{strategy.strategy_type}' for strategy {strategy.strategy_id}"
        )
        return None

    url = config.get("url")
    timeout_seconds = config.get("timeout_seconds", 2.0)
    headers = {"Content-Type": "application/json", **config.get("headers", {})}
    request_data = {
        "strategy_id": strategy.strategy_id,
        "strategy_type": strategy.strategy_type,
        "url": url,
        "payload": payload,
    }
    if not url:
        logger.warning(
            f"Inbound context strategy {strategy.strategy_id} is missing a webhook URL"
        )
        return None
    start_ms = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        context = data.get("context") if isinstance(data, dict) else None
        latency_ms = int((time.monotonic() - start_ms) * 1000)

        if not isinstance(context, dict):
            message = (
                "Inbound context lookup returned an invalid payload; "
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

        await _log_lookup(
            user_email=user_email,
            assistant_id=assistant_id,
            room_name=room_name,
            request_data=request_data,
            status="success",
            latency_ms=latency_ms,
            message="Inbound context lookup completed successfully",
            response_data={
                "context_keys": sorted(context.keys()),
                "context_size": len(context),
            },
        )
        return context

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
