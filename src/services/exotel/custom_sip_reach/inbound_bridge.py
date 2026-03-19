"""
Main inbound bridge orchestrator — handles incoming SIP INVITEs from Exotel,
wires up RTP, and connects an agent via LiveKit.
"""

import asyncio
import json
import uuid

from livekit import rtc
from livekit.api import AccessToken, VideoGrants, SIPGrants

from .config import (
    EXOTEL_CUSTOMER_IP,
    EXOTEL_CUSTOMER_SIP_PORT,
    EXOTEL_MEDIA_IP,
    LK_API_KEY,
    LK_API_SECRET,
    LK_URL,
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
    RTP_SILENCE_TIMEOUT_SECONDS,
    validate_config,
)
from .inbound_listener import register_call_id, unregister_call_id
from .port_pool import get_port_pool
from .rtp_bridge import RTPMediaBridge
from .sip_client import format_exotel_number
from src.core.db.db_schemas import Assistant, InboundSIP
from src.services.livekit.livekit_svc import LiveKitService
from src.core.logger import logger, setup_logging
setup_logging()


def _extract_sip_number(header_value: str) -> str:
    if "sip:" not in header_value:
        return "Unknown"
    return header_value.split("sip:", 1)[1].split("@", 1)[0].strip()


def _build_sip_response(
    status_line: str,
    call_id: str,
    cseq: str,
    from_header: str,
    to_header: str,
    via_headers: list[str],
) -> bytes:
    headers = [status_line]
    for via in via_headers:
        headers.append(f"Via: {via}")
    headers.append(f"From: {from_header}")
    headers.append(f"To: {to_header}")
    headers.append(f"Call-ID: {call_id}")
    headers.append(f"CSeq: {cseq}")
    headers.append("Content-Length: 0")
    return ("\r\n".join(headers) + "\r\n\r\n").encode()


async def handle_inbound_call(
    hdrs: dict,
    raw_invite: bytes,
    sdp_body: str,
    writer: asyncio.StreamWriter,
    reader: asyncio.StreamReader,
    from_header: str,
    to_header: str,
    call_id: str,
    cseq: str,
    via_headers: list[str],
    record_routes: list[str],
):
    if not validate_config():
        logger.error("[INBOUND] Config validation failed")
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 503 Service Unavailable",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        return

    livekit_service = LiveKitService()

    # Extract remote RTP endpoint from Exotel's SDP
    remote_ip, remote_port, pt = None, 0, PCMA_PAYLOAD_TYPE
    for line in sdp_body.splitlines():
        if line.startswith("c=IN IP4 "):
            remote_ip = line.split("c=IN IP4 ")[1].strip()
        elif line.startswith("m=audio "):
            parts = line.split()
            remote_port = int(parts[1])
            # Pick a real audio codec (8=PCMA, 0=PCMU), never 101 (DTMF)
            offered_pts = [int(p) for p in parts[3:] if p.isdigit()]
            for preferred in (PCMA_PAYLOAD_TYPE, PCMU_PAYLOAD_TYPE):
                if preferred in offered_pts:
                    pt = preferred
                    break
            else:
                logger.warning(f"[INBOUND] No supported audio PT in SDP: {offered_pts}")

    if not remote_ip or not remote_port:
        logger.error(
            f"[INBOUND] Failed to extract RTP info from SDP. call-id={call_id}"
        )
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 400 Bad Request",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        return

    # Extract numbers from SIP headers
    dialed_number = _extract_sip_number(to_header)
    caller_number = _extract_sip_number(from_header)
    normalized_number = format_exotel_number(dialed_number)
    
    # Log incoming call details
    logger.info(f"[INBOUND] call-id={call_id} caller={caller_number} dialed={dialed_number} normalized={normalized_number}")

    inbound_mapping = await InboundSIP.find_one(
        InboundSIP.phone_number_normalized == normalized_number,
        InboundSIP.service == "exotel",
        InboundSIP.is_active == True,
    )
    if not inbound_mapping or not inbound_mapping.assistant_id:
        logger.warning(
            f"[INBOUND] No active assistant mapping found for number '{normalized_number}' (call-id={call_id}, caller={caller_number})"
        )
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 480 Temporarily Unavailable",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        return

    assistant = await Assistant.find_one(
        Assistant.assistant_id == inbound_mapping.assistant_id,
        Assistant.assistant_is_active == True,
    )
    if not assistant:
        logger.warning(
            f"[INBOUND] No active assistant found for mapping {inbound_mapping.inbound_id}"
        )
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 480 Temporarily Unavailable",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        return

    try:
        room_name = await livekit_service.create_room(assistant.assistant_id)
    except Exception as e:
        logger.error(f"[INBOUND] Failed to create room: {e}")
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 500 Internal Server Error",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        return

    pool = get_port_pool()
    port = await pool.acquire()
    logger.info(
        f"[INBOUND] call-id={call_id} phone={normalized_number} room={room_name} rtp_port={port}"
    )

    try:
        dispatch_metadata = {
            "call_type": "inbound",
            "service": "exotel",
            "assistant_id": assistant.assistant_id,
            "assistant_name": assistant.assistant_name,
            "inbound_id": inbound_mapping.inbound_id,
            "inbound_context_strategy_id": inbound_mapping.inbound_context_strategy_id,
            "inbound_number": normalized_number,
            "caller_number": caller_number,
        }
        logger.info(
            f"[INBOUND] Creating dispatch for assistant {assistant.assistant_id} in room {room_name}"
        )
        await livekit_service.create_agent_dispatch(room_name, dispatch_metadata)
    except Exception as e:
        logger.error(f"[INBOUND] Failed to create room/dispatch: {e}")
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 500 Internal Server Error",
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        await writer.drain()
        await pool.release(port)
        return

    rtp_bridge = None
    forward_task = None
    inbound_bye = None
    room = rtc.Room()

    def build_200_ok() -> bytes:
        sdp = (
            f"v=0\r\n"
            f"o=- 0 0 IN IP4 {EXOTEL_MEDIA_IP}\r\n"
            f"s=-\r\n"
            f"c=IN IP4 {EXOTEL_MEDIA_IP}\r\n"
            f"t=0 0\r\n"
            f"m=audio {port} RTP/AVP {PCMA_PAYLOAD_TYPE} 0 101\r\n"
            f"a=rtpmap:{PCMA_PAYLOAD_TYPE} PCMA/8000\r\n"
            f"a=rtpmap:0 PCMU/8000\r\n"
            f"a=rtpmap:101 telephone-event/8000\r\n"
            f"a=fmtp:101 0-15\r\n"
            f"a=ptime:20\r\n"
            f"a=sendrecv\r\n"
        )
        h = ["SIP/2.0 200 OK"]
        for via in via_headers:
            h.append(f"Via: {via}")
        for rr in record_routes:
            h.append(f"Record-Route: {rr}")
        h.append(f"From: {from_header}")
        h.append(f"To: {to_header};tag=inbound-{port}-{uuid.uuid4().hex[:4]}")
        h.append(f"Call-ID: {call_id}")
        h.append(f"CSeq: {cseq}")
        h.append("Supported: 100rel, timer, replaces")
        h.append("Allow: INVITE, ACK, CANCEL, BYE, OPTIONS, UPDATE")
        h.append(
            f"Contact: <sip:{EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};transport=tcp>"
        )
        h.append("Content-Type: application/sdp")
        h.append(f"Content-Length: {len(sdp.encode())}")

        return ("\r\n".join(h) + "\r\n\r\n" + sdp).encode()

    try:
        inbound_bye = register_call_id(call_id)
        rtp_bridge = RTPMediaBridge(public_ip=EXOTEL_MEDIA_IP, bind_port=port)

        @room.on("track_subscribed")
        def on_track(track, publication, participant):
            nonlocal forward_task
            if (
                track.kind == rtc.TrackKind.KIND_AUDIO
                and publication.source == rtc.TrackSource.SOURCE_MICROPHONE
                and forward_task is None
            ):
                logger.info(
                    f"[INBOUND] Agent audio from {participant.identity} — buffering"
                )
                from .bridge import _forward_audio

                forward_task = asyncio.create_task(_forward_audio(track, rtp_bridge))

        token = (
            AccessToken(LK_API_KEY, LK_API_SECRET)
            .with_identity(f"sip-in-{normalized_number}")
            .with_metadata(json.dumps({"source": "exotel_bridge"}))
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .with_sip_grants(SIPGrants(admin=True, call=True))
            .to_jwt()
        )
        await room.connect(LK_URL, token)
        logger.info(f"[INBOUND] LiveKit connected: {room_name}")
        await rtp_bridge.start_inbound(room)

        # Set remote endpoint from what Exotel sent us
        rtp_bridge.set_remote_endpoint(remote_ip, remote_port, pt)

        # Send 200 OK Response
        resp_200 = build_200_ok()
        logger.info("[INBOUND] Sending 200 OK ->")
        writer.write(resp_200)
        await writer.drain()

        # Stabilization delay: wait for the agent process to finish booting
        # (session.start + TTS init) and register its data_received handler
        # before we publish call_answered. Without this, the publish fires
        # ~25ms after LiveKit connect, but the agent needs ~200-500ms to boot,
        # so the data packet arrives with no listener and is silently dropped.
        # NOTE: 200 OK is already sent above — Exotel's RTP path is live.
        # This delay only controls when we signal the agent to start speaking.
        logger.info(
            "[INBOUND] Waiting for agent to stabilize before signalling call_answered..."
        )
        await asyncio.sleep(1.5)

        # Let agent know call is connected
        try:
            await room.local_participant.publish_data(
                json.dumps({"event": "call_answered"}).encode(),
                topic="sip_bridge_events",
            )
            logger.info("[INBOUND] Published call_answered event to agent")
        except Exception as e:
            logger.error(f"[INBOUND] Failed to publish call_answered event: {e}")

        # Watch for BYE and RTP Silence
        disconnect_reason = "unknown"
        while True:
            if room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
                disconnect_reason = "livekit_disconnected"
                break

            if inbound_bye and inbound_bye.is_set():
                disconnect_reason = "sip_bye_inbound_tcp"
                break

            since_rx = rtp_bridge.seconds_since_rx()

            if (
                since_rx is not None
                and RTP_SILENCE_TIMEOUT_SECONDS > 0
                and since_rx > RTP_SILENCE_TIMEOUT_SECONDS
            ):
                disconnect_reason = "rtp_silence_after_flow"
                break

            await asyncio.sleep(1)

        logger.info(f"[INBOUND] Call ended — reason={disconnect_reason}")

    except Exception as e:
        logger.error(f"[INBOUND] Error: {e}", exc_info=True)

    finally:
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass

        if rtp_bridge:
            rtp_bridge.stop()

        await room.disconnect()
        await pool.release(port)
        logger.info(f"[INBOUND] Port {port} released")
        unregister_call_id(call_id)
