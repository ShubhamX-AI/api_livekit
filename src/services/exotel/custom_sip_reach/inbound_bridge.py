"""
Main inbound bridge orchestrator — handles incoming SIP INVITEs from Exotel,
wires up RTP, and connects an agent via LiveKit.

handle_inbound_call (main loop): SIP negotiation, DB lookups, 200 OK response.
The media half runs in its own process — see inbound_worker.py.
"""

import asyncio
import json
import queue as _stdlib_queue
import uuid

from livekit.api import AccessToken, VideoGrants, SIPGrants

from .config import (
    EXOTEL_CUSTOMER_IP,
    EXOTEL_CUSTOMER_SIP_PORT,
    EXOTEL_MEDIA_IP,
    LK_API_KEY,
    LK_API_SECRET,
    PCMA_PAYLOAD_TYPE,
    PCMU_PAYLOAD_TYPE,
    validate_config,
)
from .inbound_listener import DuplicateCallId, register_call_id, unregister_call_id
from .inbound_worker import inbound_bridge_subprocess_entry
from .port_pool import get_port_pool
from .sip_client import format_exotel_number
from src.core.db.db_schemas import Assistant, InboundSIP
from src.services.livekit.livekit_svc import LiveKitService
from src.services.outbound_dispatcher.dispatcher import (
    _reap_bridge,
    _terminate_bridge,
    _watch_agent_join,
    get_bridge_context,
    release_slot,
    try_reserve_slot,
)
from src.core.logger import logger, set_room_context


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
    sdp_body: str,
    writer: asyncio.StreamWriter,
    from_header: str,
    to_header: str,
    call_id: str,
    cseq: str,
    via_headers: list[str],
    record_routes: list[str],
    peer_ip: str | None = None,
):
    """
    Phase 1 (this coroutine, on the listener's loop): SIP validation, DB lookups, slot
    reservation, port acquisition, agent dispatch.
    Phase 2 (its own OS process, inbound_worker.py): LiveKit + RTP audio lifecycle.

    Returns once the 200 OK is sent; a monitor task owns the bridge process from there, so a
    call does not hold an INVITE setup slot for its whole duration.
    """
    # Register for cancellation *before* any DB/LiveKit work starts. Exotel sends CANCEL
    # (not BYE) when the caller hangs up before we answer, and inbound_listener.py can only
    # signal us via this registry — if registration happened later (as it used to, right
    # before the 200 OK), a CANCEL arriving during setup found nothing to signal and the
    # call got answered/dispatched anyway. The same event is reused after answer for BYE.
    try:
        registration_key, cancel_event = register_call_id(call_id, peer_ip)
    except (ValueError, DuplicateCallId) as e:
        # A missing Call-ID, or one already held by a live call. Answering either would put two
        # calls on one teardown signal, so refuse the INVITE and leave the existing call alone.
        logger.warning(f"[INBOUND] Refusing INVITE call-id={call_id!r} from {peer_ip}: {e}")
        writer.write(
            _build_sip_response(
                status_line="SIP/2.0 400 Bad Request",
                call_id=call_id or "",
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        try:
            await writer.drain()
        except Exception:
            pass
        return

    async def _reject(status_line: str, *, release: bool = False) -> None:
        """Send a SIP error/final response on the INVITE's own connection and clean up.

        Replaces the repeated build-response/drain/return blocks that used to appear at
        every early-exit point in this function (one of the "hard to follow" spots flagged
        for simplification) — one place to get the cleanup right.
        """
        writer.write(
            _build_sip_response(
                status_line=status_line,
                call_id=call_id,
                cseq=cseq,
                from_header=from_header,
                to_header=to_header,
                via_headers=via_headers,
            )
        )
        try:
            await writer.drain()
        except Exception as drain_err:
            logger.debug(f"[INBOUND] writer.drain() during reject failed: {drain_err}")
        if release:
            release_slot()
        unregister_call_id(registration_key)

    if not validate_config():
        logger.error("[INBOUND] Config validation failed")
        await _reject("SIP/2.0 503 Service Unavailable")
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
        await _reject("SIP/2.0 400 Bad Request")
        return

    if cancel_event.is_set():
        logger.info(f"[INBOUND] Caller cancelled before setup — call-id={call_id}")
        await _reject("SIP/2.0 487 Request Terminated")
        return

    dialed_number = _extract_sip_number(to_header)
    caller_number = _extract_sip_number(from_header)
    normalized_number = format_exotel_number(dialed_number)

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
        await _reject("SIP/2.0 480 Temporarily Unavailable")
        return

    assistant = await Assistant.find_one(
        Assistant.assistant_id == inbound_mapping.assistant_id,
        Assistant.assistant_is_active == True,
    )
    if not assistant:
        logger.warning(
            f"[INBOUND] No active assistant found for mapping {inbound_mapping.inbound_id}"
        )
        await _reject("SIP/2.0 480 Temporarily Unavailable")
        return

    if cancel_event.is_set():
        logger.info(f"[INBOUND] Caller cancelled before setup — call-id={call_id}")
        await _reject("SIP/2.0 487 Request Terminated")
        return

    if not await try_reserve_slot():
        logger.warning(
            f"[INBOUND] Slot cap reached — rejecting call-id={call_id} "
            f"caller={caller_number} dialed={normalized_number}"
        )
        await _reject("SIP/2.0 486 Busy Here")
        return

    try:
        room_name = await livekit_service.create_room(assistant.assistant_id)
        set_room_context(room_name, global_fallback=False)
        logger.info(f"[INBOUND] SIP call_id={call_id} mapped to room={room_name}")
    except Exception as e:
        logger.error(f"[INBOUND] Failed to create room: {e}")
        await _reject("SIP/2.0 500 Internal Server Error", release=True)
        return

    if cancel_event.is_set():
        logger.info(f"[INBOUND] Caller cancelled before setup — call-id={call_id}")
        await _reject("SIP/2.0 487 Request Terminated", release=True)
        return

    try:
        await livekit_service.initialize_call_record(
            room_name=room_name,
            assistant_id=assistant.assistant_id,
            assistant_name=assistant.assistant_name,
            to_number=caller_number,
            call_status="initiated",
            created_by_email=assistant.assistant_created_by_email,
            call_type="inbound",
            call_service="exotel",
            platform_number=normalized_number,
        )
    except Exception as e:
        logger.error(f"[INBOUND] Failed to initialize call record: {e}")
        await _reject("SIP/2.0 500 Internal Server Error", release=True)
        return

    # Release in-memory reservation; CallRecord (status="initiated") now tracked via DB.
    release_slot()

    if cancel_event.is_set():
        logger.info(f"[INBOUND] Caller cancelled before setup — call-id={call_id}")
        await _reject("SIP/2.0 487 Request Terminated")
        return

    pool = get_port_pool()
    try:
        port = pool.acquire()
    except RuntimeError as e:
        # Pool exhaustion used to escape this coroutine entirely (it ran as a bare task), so
        # the INVITE got no SIP response at all and the caller heard dead air until Exotel
        # timed out. Answer properly instead.
        logger.error(f"[INBOUND] No RTP port for call-id={call_id}: {e}")
        await _reject("SIP/2.0 486 Busy Here")
        return
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
        await _reject("SIP/2.0 500 Internal Server Error")
        pool.release(port)
        return

    if cancel_event.is_set():
        logger.info(f"[INBOUND] Caller cancelled before setup — call-id={call_id}")
        await _reject("SIP/2.0 487 Request Terminated")
        pool.release(port)
        return

    # Nothing here confirms the dispatched agent ever actually joins and runs — this
    # watches the CallRecord and force-ends the call if it doesn't, instead of leaving it
    # silently occupying the line under load. Same watchdog used for outbound calls.
    # already_answered=True: inbound calls never write call_status="answered" (the 200 OK
    # about to be sent below *is* the answer, tracked only on the SIP side).
    asyncio.create_task(
        _watch_agent_join(room_name, assistant.assistant_id, already_answered=True)
    )

    # Reuse the event registered at the top of this function — it now also carries
    # inbound BYE detection (post-answer) for the bridge process.
    inbound_bye = cancel_event

    token = (
        AccessToken(LK_API_KEY, LK_API_SECRET)
        .with_identity(f"sip-in-{normalized_number}-{uuid.uuid4().hex[:6]}")
        .with_metadata(json.dumps({"source": "exotel_bridge"}))
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .with_sip_grants(SIPGrants(admin=True, call=True))
        .to_jwt()
    )

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

    # ── Phase 2: media bridge runs in its own OS process ─────────────────────
    # It was a thread per call inside this process. See inbound_worker.py for why that stopped
    # working at load. The process binds the RTP socket and reports back before we answer, so
    # Exotel never sends RTP at a port nothing is listening on.
    ctx = get_bridge_context()
    ready_queue = ctx.Queue()
    answered_event = ctx.Event()

    bridge_process = ctx.Process(
        target=inbound_bridge_subprocess_entry,
        args=(room_name, port, remote_ip, remote_port, pt, token,
              ready_queue, answered_event, inbound_bye),
        daemon=True,
        name=f"bridge-in-{normalized_number}",
    )
    bridge_process.start()

    ready = await _wait_for_bridge_ready(ready_queue, bridge_process)
    if not ready:
        logger.error(f"[INBOUND] Bridge process never became ready — call-id={call_id}")
        _terminate_bridge(bridge_process)
        # Reap before releasing: SIGTERM is asynchronous, and the port must not go back into
        # the pool while the dying process still holds its RTP socket open.
        await asyncio.to_thread(_reap_bridge, bridge_process)
        await _reject("SIP/2.0 503 Service Unavailable")
        pool.release(port)
        return

    logger.info("[INBOUND] Sending 200 OK ->")
    writer.write(build_200_ok())
    await writer.drain()
    answered_event.set()

    # Hand the process off to a monitor and return, so this call stops occupying an INVITE
    # setup slot for its whole duration.
    asyncio.create_task(
        _monitor_inbound_bridge(bridge_process, port, registration_key, room_name)
    )


async def _wait_for_bridge_ready(ready_queue, bridge_process, timeout: float = 20.0) -> bool:
    """Wait for the bridge process to report that its RTP socket and room are up.

    Kept comfortably under Exotel's INVITE timeout: this wait holds an INVITE setup slot, so a
    long one would queue the calls behind it. It must still exceed the worker's own 15 second
    LiveKit connect timeout, so a connect failure is reported rather than timed out blindly.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            result = ready_queue.get_nowait()
        except _stdlib_queue.Empty:
            if not bridge_process.is_alive():
                logger.error("[INBOUND] Bridge process exited before signalling ready")
                return False
            await asyncio.sleep(0.1)
            continue
        if result.get("ready"):
            return True
        logger.error(f"[INBOUND] Bridge process failed to start: {result.get('error')}")
        return False
    return False


async def _monitor_inbound_bridge(
    bridge_process, port: int, registration_key: str, room_name: str
) -> None:
    """Release the port and the registry entry however the bridge process ends."""
    try:
        while bridge_process.is_alive():
            await asyncio.sleep(2.0)
    finally:
        # This runs in a bare task, so anything raising here would vanish as an unretrieved
        # task exception and strand the port and the registry entry. Each step stands alone.
        try:
            await asyncio.to_thread(_reap_bridge, bridge_process)
        except Exception as e:
            logger.warning(f"[INBOUND] Reaping bridge process failed: {e}")
        try:
            get_port_pool().release(port)
        except Exception as e:
            logger.error(f"[INBOUND] Releasing port {port} failed: {e}", exc_info=True)
        try:
            unregister_call_id(registration_key)
        except Exception as e:
            logger.warning(f"[INBOUND] Unregistering {registration_key} failed: {e}")
        logger.info(f"[INBOUND] Bridge finished room={room_name}, port {port} released")
