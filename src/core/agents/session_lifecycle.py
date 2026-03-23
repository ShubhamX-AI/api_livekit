"""Call readiness gating and recording management for the agent session."""

import asyncio

from src.core.logger import logger


class CallReadinessGate:
    """Single gate that controls all agent activity for Exotel outbound calls.

    For non-Exotel calls the gate is open immediately.
    For Exotel outbound calls the gate stays closed until `mark_answered()` is called.
    """

    def __init__(self, is_exotel_outbound: bool):
        self._ready = asyncio.Event()
        if not is_exotel_outbound:
            self._ready.set()  # Non-Exotel calls are ready immediately

    @property
    def is_active(self) -> bool:
        """True when the agent should process events (transcription, filler, etc.)."""
        return self._ready.is_set()

    def mark_answered(self):
        """Signal that the remote party has picked up."""
        self._ready.set()

    async def wait_until_ready(self, timeout: float = 60.0) -> bool:
        """Block until the call is answered or timeout expires. Returns True if answered."""
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


class RecordingManager:
    """Encapsulates room recording with retry logic."""

    def __init__(self, livekit_services, room_name: str, assistant_id: str):
        self._livekit_services = livekit_services
        self._room_name = room_name
        self._assistant_id = assistant_id
        self._start_task: asyncio.Task | None = None
        self._start_done = asyncio.Event()
        self._start_success = False
        self.s3_url: str | None = None
        self.egress_id: str | None = None

    async def _start_with_retries(self) -> bool:
        """Start recording with retries and store result state."""
        max_retries = 2

        for attempt in range(1, max_retries + 1):
            try:
                recording_info = await self._livekit_services.start_room_recording(
                    room_name=self._room_name,
                    assistant_id=self._assistant_id,
                )
                if recording_info and recording_info.get("success"):
                    recording_data = recording_info.get("data")
                    if isinstance(recording_data, dict):
                        self.s3_url = recording_data.get("s3_url")
                        self.egress_id = recording_data.get("egress_id")
                        logger.info(
                            f"Recording started | egress_id={self.egress_id} | S3={self.s3_url}"
                        )
                    return True
                logger.warning(
                    f"Recording attempt {attempt}/{max_retries} returned failure: {recording_info}"
                )
            except Exception as e:
                logger.error(
                    f"Recording attempt {attempt}/{max_retries} failed: {e}",
                    exc_info=True,
                )

            if attempt < max_retries:
                await asyncio.sleep(2)

        logger.error("Recording failed after all retries — call will proceed without recording")
        return False

    async def start_once(self):
        """Start recording once and return whether start succeeded."""
        if self._start_task is None:
            self._start_task = asyncio.create_task(self._start_with_retries())
            self._start_task.add_done_callback(lambda _: self._start_done.set())
        await self._start_done.wait()
        if self._start_task and not self._start_task.cancelled():
            self._start_success = bool(self._start_task.result())
        return self._start_success

    async def ensure_started(self, timeout: float) -> bool:
        """Start recording if needed and wait up to timeout seconds for completion."""
        if self._start_task is None:
            self._start_task = asyncio.create_task(self._start_with_retries())
            self._start_task.add_done_callback(lambda _: self._start_done.set())
        try:
            await asyncio.wait_for(self._start_done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timed out waiting for recording start after {timeout:.1f}s")
            return False
        if self._start_task and not self._start_task.cancelled():
            self._start_success = bool(self._start_task.result())
        return self._start_success
