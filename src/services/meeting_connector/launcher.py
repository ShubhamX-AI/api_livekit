"""Start and stop the container that joins a meeting on our behalf.

The connector is a separate service (see ``agent-tracking/plan/01-meet-connector-service.md``).
We only ever do two things to it: launch one with a fixed environment block, and kill it.

It is launched per call rather than kept running, so this is ``docker run --rm -d`` through a
subprocess — no Docker SDK dependency, no long-lived client. The three LiveKit secrets and the
status token are handed over through the subprocess's own environment and referenced by name on
the command line, so they never appear in ``ps`` output or in the shell history of whoever is
debugging the host.
"""

import asyncio
import os

from src.core.config import settings
from src.core.logger import logger

from .platforms import connector_image

#: Env vars passed by name only. Docker reads each from the environment we hand the subprocess.
_SECRET_ENV_NAMES = (
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "CONNECTOR_STATUS_TOKEN",
)

_LAUNCH_TIMEOUT_SECONDS = 60
_STOP_TIMEOUT_SECONDS = 30


def _status_url() -> str:
    return settings.MEETING_CONNECTOR_STATUS_URL or f"{settings.BACKEND_URL.rstrip('/')}/meeting_call/status"


async def launch_connector(
    *,
    platform: str,
    meeting_url: str,
    room_name: str,
    bot_display_name: str,
) -> str:
    """Start a connector for one meeting and return its container id.

    ``LIVEKIT_SOURCE_PUBLISH_ON_BEHALF`` is set to the room name, and the agent sets the matching
    ``lk.publish_on_behalf`` attribute on itself once its session starts. That is how the
    connector recognises which LiveKit participant to play into the meeting without knowing the
    agent's identity, which the LiveKit server mints inside the job token and nobody can predict
    beforehand.
    """
    visible_env = {
        "MEETING_URL": meeting_url,
        "BOT_DISPLAY_NAME": bot_display_name,
        "LIVEKIT_URL": settings.LIVEKIT_URL,
        "LIVEKIT_ROOM": room_name,
        "LIVEKIT_SOURCE_PUBLISH_ON_BEHALF": room_name,
        "CONNECTOR_STATUS_URL": _status_url(),
    }

    argv = ["docker", "run", "--rm", "-d", "--network", "host"]
    for name, value in visible_env.items():
        argv += ["-e", f"{name}={value}"]
    for name in _SECRET_ENV_NAMES:
        argv += ["-e", name]
    argv.append(connector_image(platform))

    subprocess_env = {
        **os.environ,
        "LIVEKIT_API_KEY": settings.LIVEKIT_API_KEY,
        "LIVEKIT_API_SECRET": settings.LIVEKIT_API_SECRET,
        "CONNECTOR_STATUS_TOKEN": settings.MEETING_CONNECTOR_STATUS_TOKEN,
    }

    process = await asyncio.create_subprocess_exec(
        *argv,
        env=subprocess_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), _LAUNCH_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        raise RuntimeError("Timed out starting the meeting connector container") from None

    if process.returncode != 0:
        raise RuntimeError(
            f"Meeting connector container failed to start: {stderr.decode(errors='replace').strip()}"
        )

    container_id = stdout.decode(errors="replace").strip()
    if not container_id:
        raise RuntimeError("Meeting connector container started but reported no container id")

    logger.info(f"Started {platform} connector {container_id[:12]} for room {room_name}")
    return container_id


async def stop_connector(container_id: str) -> None:
    """Kill a connector container. Never raises — the call is already over either way."""
    if not container_id:
        return
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "kill",
            container_id,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), _STOP_TIMEOUT_SECONDS)
        if process.returncode != 0:
            # Already gone is the common case: the connector exits by itself when the meeting
            # ends, and `--rm` removes it, so `docker kill` then has nothing to kill.
            logger.info(
                f"Meeting connector {container_id[:12]} was not running: "
                f"{stderr.decode(errors='replace').strip()}"
            )
    except (OSError, TimeoutError) as e:
        logger.warning(f"Failed to stop meeting connector {container_id[:12]}: {e}")
