from __future__ import annotations

import asyncio
from typing import Callable

from livekit import rtc
from livekit.agents import stt as stt_pkg
from livekit.plugins import sarvam as sarvam_plugin

from src.core.agents.audio_denoise import SpeechGate
from src.core.config import settings
from src.core.logger import logger


async def run_sarvam_parallel_stt(
    *,
    room: rtc.Room,
    target_identity: str,
    on_final: Callable[[str], None],
    stop_event: asyncio.Event,
    api_key: str | None = None,
) -> None:
    """Stream caller audio into Sarvam Saras v3 and invoke `on_final` for each finalized utterance.

    Runs alongside OpenAI Realtime — does not touch the LLM audio pipeline.
    Exits when `stop_event` is set.
    """
    sarvam_stt = sarvam_plugin.STT(
        model="saaras:v3",
        mode="codemix",
        language="unknown",
        api_key=api_key or settings.SARVAM_API_KEY,
        sample_rate=16000,
    )
    stream = sarvam_stt.stream()
    pump_task: asyncio.Task | None = None

    async def _pump(track: rtc.Track) -> None:
        # This tap opens its own AudioStream, so it does not inherit the SpeechGate that
        # RoomIO applies to the LLM's input — it needs its own instance (the APM and VAD
        # are both stateful per stream). Gating here also keeps Sarvam from transcribing
        # noise, which is what produced the hallucinated scripts described in
        # docs/architecture/audio-pipeline.md.
        audio = rtc.AudioStream(
            track, sample_rate=16000, num_channels=1, noise_cancellation=SpeechGate()
        )
        try:
            async for ev in audio:
                if stop_event.is_set():
                    break
                stream.push_frame(ev.frame)
        except Exception as e:
            logger.error(f"[SARVAM-STT] Audio pump error: {e}", exc_info=True)

    def _on_track(track, _pub, participant) -> None:
        nonlocal pump_task
        if participant.identity != target_identity:
            return
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if pump_task and not pump_task.done():
            return
        logger.info(f"[SARVAM-STT] Attaching to {participant.identity} audio track")
        pump_task = asyncio.create_task(_pump(track))

    # Late-bind if track already exists
    for p in room.remote_participants.values():
        for pub in p.track_publications.values():
            if pub.track:
                _on_track(pub.track, pub, p)

    room.on("track_subscribed", _on_track)

    try:
        async for ev in stream:
            if stop_event.is_set():
                break
            if ev.type == stt_pkg.SpeechEventType.FINAL_TRANSCRIPT:
                text = ev.alternatives[0].text if ev.alternatives else ""
                if text.strip():
                    try:
                        on_final(text)
                    except Exception as e:
                        logger.error(f"[SARVAM-STT] on_final callback error: {e}")
    except Exception as e:
        logger.error(f"[SARVAM-STT] Stream error: {e}", exc_info=True)
    finally:
        room.off("track_subscribed", _on_track)
        if pump_task:
            pump_task.cancel()
            await asyncio.gather(pump_task, return_exceptions=True)
        try:
            await stream.aclose()
        except Exception as e:
            logger.debug(f"[SARVAM-STT] aclose error: {e}")
        logger.info("[SARVAM-STT] Parallel STT stopped")