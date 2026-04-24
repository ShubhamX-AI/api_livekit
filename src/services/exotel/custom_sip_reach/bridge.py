"""
Main bridge orchestrator — wires SIP, RTP, and LiveKit together.

run_bridge() is the single entry point that:
  1. Acquires a port from the pool
  2. Connects to LiveKit and publishes the SIP audio track
  3. Sends a SIP INVITE to Exotel
  4. Monitors for hang-up signals (BYE, RTP silence, LiveKit disconnect)
  5. Cleans up everything on exit
"""

import asyncio
import concurrent.futures
import json
import logging
import time
import uuid

from livekit import rtc
from livekit.api import AccessToken, VideoGrants, SIPGrants

from .config import (
    EXOTEL_MEDIA_IP,
    LK_API_KEY,
    LK_API_SECRET,
    LK_URL,
    NO_RTP_AFTER_ANSWER_SECONDS,
    RTP_SILENCE_TIMEOUT_SECONDS,
    validate_config,
)
from .inbound_listener import (
    register_call_id,
    unregister_call_id,
)
from .port_pool import get_port_pool
from .rtp_bridge import RTPMediaBridge
from .sip_client import ExotelSipClient
from src.core.logger import logger, setup_logging

setup_logging()


async def run_bridge(
    phone_number: str,
    room_name: str | None = None,
    sip_config: dict | None = None,
    result_signal: concurrent.futures.Future | None = None,
):
    if not validate_config():
        return

    if not LK_URL or not LK_API_KEY or not LK_API_SECRET:
        logger.error("[BRIDGE] Missing LiveKit configuration")
        return

    if not room_name:
        room_name = f"sip-bridge-{phone_number}-{uuid.uuid4().hex[:6]}"

    sip_config = sip_config or {}
    caller_id = sip_config.get("exotel_number")
    sip_host = sip_config.get("sip_host")
    sip_port = sip_config.get("sip_port")
    sip_domain = sip_config.get("sip_domain")

    pool = get_port_pool()
    port = pool.acquire()
    logger.info(f"[BRIDGE] phone={phone_number} room={room_name} rtp_port={port}")

    rtp_bridge = None
    sip_client = None
    inbound_bye = None
    ended_by_remote_bye = False
    room = rtc.Room()

    try:
        rtp_bridge = RTPMediaBridge(public_ip=EXOTEL_MEDIA_IP, bind_port=port)

        sip_client_kwargs = {"callee": phone_number, "rtp_port": port}
        if caller_id:
            sip_client_kwargs["caller_id"] = caller_id
        if sip_host:
            sip_client_kwargs["sip_host"] = sip_host
        if sip_port:
            sip_client_kwargs["sip_port"] = int(sip_port)
        if sip_domain:
            sip_client_kwargs["from_domain"] = sip_domain

        sip_client = ExotelSipClient(**sip_client_kwargs)
        inbound_bye = register_call_id(sip_client.call_id)

        # Hold/resume detection via SIP re-INVITE
        async def _on_hold_change(is_hold: bool):
            event_name = "call_hold" if is_hold else "call_resume"
            try:
                await room.local_participant.publish_data(
                    json.dumps({"event": event_name}).encode(),
                    topic="sip_bridge_events",
                )
                logger.info(f"[BRIDGE] Published {event_name}")
            except Exception as e:
                logger.error(f"[BRIDGE] Failed to publish {event_name}: {e}")

        sip_client.on_hold_change = lambda h: asyncio.create_task(_on_hold_change(h))

        # Subscribe to ALL audio tracks (agent voice + background/thinking sounds)
        @room.on("track_subscribed")
        def on_track(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(
                    f"[BRIDGE] Audio track from {participant.identity} "
                    f"(source={publication.source}) — adding to mixer"
                )
                rtp_bridge.add_outbound_track(track)
                rtp_bridge.start_outbound_mixer()

        token = (
            AccessToken(LK_API_KEY, LK_API_SECRET)
            .with_identity(f"sip-{phone_number}")
            .with_metadata(json.dumps({"source": "exotel_bridge"}))
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .with_sip_grants(SIPGrants(admin=True, call=True))
            .to_jwt()
        )
        await asyncio.wait_for(room.connect(LK_URL, token), timeout=15.0)
        logger.info(f"[BRIDGE] LiveKit connected: {room_name}")
        await rtp_bridge.start_inbound(room)

        await sip_client.connect()
        res = await sip_client.send_invite()
        if not res:
            logger.error("[BRIDGE] SIP failed")
            if result_signal is not None and not result_signal.done():
                error = sip_client.last_sip_error or "SIP INVITE failed"
                result_signal.set_result(
                    {
                        "success": False,
                        "call_status": sip_client.last_call_status or "failed",
                        "sip_status_code": sip_client.last_sip_status_code,
                        "sip_status_text": sip_client.last_sip_status_reason,
                        "error": error,
                    }
                )
            return

        # Signal the API that the call is established; bridge loop continues below
        if result_signal is not None and not result_signal.done():
            result_signal.set_result(
                {
                    "success": True,
                    "call_status": "answered",
                    "room_name": room_name,
                }
            )

        # Flush buffered agent audio + open RTP path
        rtp_bridge.set_remote_endpoint(res["remote_ip"], res["remote_port"], res["pt"])

        answered_at = time.time()

        # Notify agent that call is answered
        try:
            # Add an samll delay to avoid race conditions
            await asyncio.sleep(0.5)
            await room.local_participant.publish_data(
                json.dumps({"event": "call_answered"}).encode(),
                topic="sip_bridge_events",
            )
            logger.info("[BRIDGE] Published call_answered event")
        except Exception as e:
            logger.error(f"[BRIDGE] Failed to publish call_answered event: {e}")

        disconnect_reason = "unknown"
        sip_mon = asyncio.create_task(sip_client.wait_for_disconnection())
        while True:
            # ── Signal 1: LiveKit room disconnected ──
            if room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
                disconnect_reason = "livekit_disconnected"
                logger.info("[BRIDGE] LiveKit room disconnected")
                break

            # ── Signal 2: SIP BYE on outbound TCP (same connection as INVITE) ──
            if sip_mon.done():
                disconnect_reason = "sip_bye_outbound_tcp"
                ended_by_remote_bye = True
                logger.info("[BRIDGE] SIP BYE received on outbound TCP")
                break

            # ── Signal 3: SIP BYE on inbound TCP listener (new connection from Exotel) ──
            if inbound_bye and inbound_bye.is_set():
                disconnect_reason = "sip_bye_inbound_tcp"
                ended_by_remote_bye = True
                logger.info("[BRIDGE] SIP BYE received on inbound TCP listener")
                break

            since_rx = rtp_bridge.seconds_since_rx()

            # ── Signal 4: No RTP ever arrived after answer — call setup failure ──
            if (
                since_rx is None
                and NO_RTP_AFTER_ANSWER_SECONDS > 0
                and (time.time() - answered_at) > NO_RTP_AFTER_ANSWER_SECONDS
            ):
                disconnect_reason = "no_rtp_after_answer"
                logger.error(
                    "[RTP] No inbound RTP after %ss — call never connected, ending",
                    NO_RTP_AFTER_ANSWER_SECONDS,
                )
                break

            # ── Signal 5: RTP was flowing but stopped — caller hung up ──
            if (
                since_rx is not None
                and RTP_SILENCE_TIMEOUT_SECONDS > 0
                and since_rx > RTP_SILENCE_TIMEOUT_SECONDS
            ):
                disconnect_reason = "rtp_silence_after_flow"
                logger.info(
                    "[RTP] No audio for %.0fs (threshold=%ss) — caller hung up",
                    since_rx,
                    RTP_SILENCE_TIMEOUT_SECONDS,
                )
                break

            await asyncio.sleep(1)

        logger.info(f"[BRIDGE] Call ended — reason={disconnect_reason}")

    except Exception as e:
        logger.error(f"[BRIDGE] Error: {e}", exc_info=True)
        # Signal failure if crash happened before the INVITE resolved
        if result_signal is not None and not result_signal.done():
            try:
                call_status = "failed"
                sip_status_code = None
                sip_status_text = str(e)
                if sip_client:
                    call_status = sip_client.last_call_status or "failed"
                    sip_status_code = sip_client.last_sip_status_code
                    sip_status_text = sip_client.last_sip_status_reason or str(e)
                result_signal.set_result(
                    {
                        "success": False,
                        "call_status": call_status,
                        "sip_status_code": sip_status_code,
                        "sip_status_text": sip_status_text,
                        "error": str(e),
                    }
                )
            except concurrent.futures.InvalidStateError:
                pass  # already signaled

    finally:
        if sip_client:
            if not ended_by_remote_bye:
                await sip_client.send_bye()
            await sip_client.close()

        if rtp_bridge:
            rtp_bridge.stop()

        await room.disconnect()
        pool.release(port)
        logger.info(f"[BRIDGE] Port {port} released")
        if sip_client:
            unregister_call_id(sip_client.call_id)
