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
        self._started = False
        self.s3_url: str | None = None

    async def start_once(self):
        """Start recording with retries. No-op if already started."""
        if self._started:
            return
        self._started = True
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
                        logger.info(f"Recording started | S3: {self.s3_url}")
                    return
                else:
                    logger.warning(f"Recording attempt {attempt}/{max_retries} returned failure: {recording_info}")
            except Exception as e:
                logger.error(f"Recording attempt {attempt}/{max_retries} failed: {e}", exc_info=True)

            if attempt < max_retries:
                await asyncio.sleep(2)

        logger.error("Recording failed after all retries — call will proceed without recording")
