"""GET /health — one deep probe of every dependency an API request needs.

Always answers HTTP 200: a degraded dependency shows up in the body, never as a 5xx, so a
MongoDB or LiveKit blip can't get every API container pulled out of rotation at once (the
compose healthcheck only asks whether the route answers). Read `data.status` / `data.checks`,
not the status code. If an orchestrator ever needs to gate traffic, add a separate
`/health/ready` rather than overloading this one.
"""

import asyncio
import time

from fastapi import APIRouter

from src.api.models.response_models import apiResponse
from src.core.config import settings
from src.core.db.database import ping_db
from src.core.logger import logger
from src.core.providers.keys import redact_text
from src.core.version import __version__
from src.services.livekit.livekit_svc import LiveKitService

router = APIRouter()

_STARTED = time.monotonic()


async def _timed(coro) -> dict:
    """Run one probe under the health deadline; any failure becomes `error` text, never a 500."""
    t0 = time.perf_counter()
    error = None
    try:
        await asyncio.wait_for(coro, settings.HEALTH_PROBE_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001 — the broad catch is the point: one broken probe must not 500 /health
        detail = redact_text(str(e))[:200]
        error = f"{type(e).__name__}: {detail}" if detail else type(e).__name__
    result = {"ok": error is None, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    if error:
        result["error"] = error
    return result


@router.get("/health")
async def health():
    probes = {"mongodb": ping_db(), "livekit": LiveKitService().ping()}
    results = await asyncio.gather(*(_timed(c) for c in probes.values()))
    checks = dict(zip(probes, results))

    healthy = all(c["ok"] for c in checks.values())
    if not healthy:
        logger.warning(f"health degraded: {[n for n, c in checks.items() if not c['ok']]}")
    status = "ok" if healthy else "degraded"
    return apiResponse(
        success=healthy,
        message=status,
        data={
            "status": status,
            "version": __version__,
            "uptime_s": round(time.monotonic() - _STARTED, 1),
            "checks": checks,
        },
    )
