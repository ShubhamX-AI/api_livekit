import asyncio
import uuid
from datetime import datetime, timezone

from beanie.operators import In

from src.core.db.db_schemas import CallRecord, OutboundCallQueue, OutboundSIP
from src.core.logger import logger
from src.services.livekit.livekit_svc import LiveKitService

MAX_CONCURRENT_JOBS = 8   # max simultaneous active sessions
MAX_RETRIES = 3           # permanent failure after this many attempts

livekit_services = LiveKitService()

# Event-driven dispatch: set by notify_dispatcher() whenever a call is enqueued.
# Dispatcher sleeps until this fires, then processes immediately.
_new_call_event = asyncio.Event()

# In-memory reservation counter: tracks calls that are mid-dispatch
# (room created but CallRecord not yet written). Prevents double-dispatch.
_dispatching_count = 0


def notify_dispatcher() -> None:
    """Call this after inserting a new OutboundCallQueue item to wake the dispatcher."""
    _new_call_event.set()


async def _get_active_session_count() -> int:
    """Count calls that are live (initiated/answered) PLUS any mid-dispatch reservations."""
    db_active = await CallRecord.find(
        In(CallRecord.call_status, ["initiated", "answered"])
    ).count()
    return db_active + _dispatching_count


async def _monitor_exotel_result(
    room_name: str, assistant_id: str, result_signal: asyncio.Queue
) -> None:
    """Mirror of the monitor logic from call.py — runs as a background task per call."""
    try:
        try:
            sip_result = await asyncio.wait_for(result_signal.get(), timeout=60.0)
        except asyncio.TimeoutError:
            await livekit_services.update_call_status(
                room_name=room_name,
                call_status="timeout",
                call_status_reason="SIP call setup timed out",
                sip_status_code=None,
                sip_status_text="SIP timeout",
                ended_at=datetime.now(timezone.utc),
                call_duration_minutes=0,
            )
            await livekit_services.send_end_call_webhook(
                room_name=room_name, assistant_id=assistant_id
            )
            logger.warning(f"Exotel SIP setup timed out | room={room_name}")
            return

        if not sip_result.get("success"):
            await livekit_services.update_call_status(
                room_name=room_name,
                call_status=sip_result.get("call_status", "failed"),
                call_status_reason=sip_result.get("error", "unknown"),
                sip_status_code=sip_result.get("sip_status_code"),
                sip_status_text=sip_result.get("sip_status_text"),
                ended_at=datetime.now(timezone.utc),
                call_duration_minutes=0,
            )
            await livekit_services.send_end_call_webhook(
                room_name=room_name, assistant_id=assistant_id
            )
            logger.warning(
                f"Exotel SIP setup failed | room={room_name} | reason={sip_result.get('error', 'unknown')}"
            )
            return

        logger.info(
            f"Exotel SIP answered | room={room_name} — status update deferred to agent session"
        )

    except Exception as e:
        logger.error(f"Exotel monitor crashed | room={room_name}: {e}", exc_info=True)
        try:
            await livekit_services.update_call_status(
                room_name=room_name,
                call_status="failed",
                call_status_reason=f"Monitor error: {e}",
                ended_at=datetime.now(timezone.utc),
                call_duration_minutes=0,
            )
            await livekit_services.send_end_call_webhook(
                room_name=room_name, assistant_id=assistant_id
            )
        except Exception:
            pass


async def _dispatch_queued_call(item: OutboundCallQueue) -> None:
    """Perform the actual LiveKit room creation + SIP dispatch for one queued call."""
    global _dispatching_count
    _dispatching_count += 1  # reserve slot immediately
    try:
        trunk = await OutboundSIP.find_one(
            OutboundSIP.trunk_id == item.trunk_id,
            OutboundSIP.trunk_is_active == True,
        )
        if not trunk:
            raise ValueError(f"Trunk {item.trunk_id} not found or inactive")

        room_name = await livekit_services.create_room(item.assistant_id)

        job_metadata = dict(item.job_metadata)
        job_metadata["to_number"] = item.to_number
        job_metadata["call_service"] = item.call_service

        await livekit_services.create_agent_dispatch(room_name, job_metadata)

        if item.call_service == "twilio":
            await livekit_services.initialize_call_record(
                room_name=room_name,
                assistant_id=item.assistant_id,
                assistant_name=item.assistant_name,
                to_number=item.to_number,
                call_status="initiated",
                created_by_email=item.user_email,
                call_type="outbound",
                call_service="twilio",
                platform_number=(trunk.trunk_config.get("numbers") or [None])[0],
            )
            await livekit_services.create_sip_participant(
                room_name=room_name,
                to_number=item.to_number,
                trunk_id=item.trunk_id,
                participant_identity=uuid.uuid4().hex,
            )

        elif item.call_service == "exotel":
            from src.services.exotel.custom_sip_reach.bridge import run_bridge

            sip_config = trunk.trunk_config
            await livekit_services.initialize_call_record(
                room_name=room_name,
                assistant_id=item.assistant_id,
                assistant_name=item.assistant_name,
                to_number=item.to_number,
                call_status="initiated",
                created_by_email=item.user_email,
                call_type="outbound",
                call_service="exotel",
                platform_number=sip_config.get("exotel_number"),
            )
            result_signal: asyncio.Queue = asyncio.Queue(maxsize=1)
            asyncio.create_task(
                run_bridge(
                    phone_number=item.to_number,
                    room_name=room_name,
                    sip_config=sip_config,
                    result_signal=result_signal,
                )
            )
            asyncio.create_task(
                _monitor_exotel_result(room_name, item.assistant_id, result_signal)
            )

        item.status = "dispatched"
        item.dispatched_at = datetime.now(timezone.utc)
        await item.save()
        logger.info(
            f"Dispatched queued call {item.queue_id} → room={room_name} | to={item.to_number}"
        )

    except Exception as e:
        logger.error(
            f"Failed to dispatch queued call {item.queue_id}: {e}", exc_info=True
        )
        item.retry_count += 1
        item.last_error = str(e)
        if item.retry_count >= MAX_RETRIES:
            item.status = "failed"
            logger.error(
                f"Queued call {item.queue_id} permanently failed after {MAX_RETRIES} retries"
            )
        else:
            item.status = "pending"
            logger.warning(
                f"Queued call {item.queue_id} will retry "
                f"(attempt {item.retry_count}/{MAX_RETRIES})"
            )
        await item.save()

    finally:
        _dispatching_count = max(0, _dispatching_count - 1)  # release reservation


async def _process_pending() -> None:
    """Check queue and dispatch as many calls as current capacity allows."""
    try:
        active = await _get_active_session_count()
        slots = MAX_CONCURRENT_JOBS - active

        if slots > 0:
            pending = (
                await OutboundCallQueue.find(OutboundCallQueue.status == "pending")
                .sort("queued_at")
                .limit(slots)
                .to_list()
            )
            for item in pending:
                item.status = "dispatching"
                await item.save()
                asyncio.create_task(_dispatch_queued_call(item))

            if pending:
                logger.info(
                    f"Dispatcher: active={active}, slots={slots}, "
                    f"dispatching {len(pending)} call(s)"
                )
    except Exception as e:
        logger.error(f"Dispatcher process error: {e}", exc_info=True)


async def outbound_dispatcher_loop() -> None:
    """Event-driven dispatcher: wakes instantly when a call is enqueued.

    Falls back to a 60s poll to catch any items left pending after a restart.
    Zero CPU usage when the queue is empty.
    """
    logger.info(f"Outbound call dispatcher started (max_concurrent={MAX_CONCURRENT_JOBS})")

    # Startup recovery: process any calls that were pending before last restart
    await _process_pending()

    while True:
        try:
            # Sleep until notify_dispatcher() fires, with a 60s fallback
            await asyncio.wait_for(_new_call_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            pass  # fallback poll — catches stuck items
        finally:
            _new_call_event.clear()

        await _process_pending()
