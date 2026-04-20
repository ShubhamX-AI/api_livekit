import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from beanie.operators import In

from src.core.config import settings
from src.core.db.database import Database
from src.core.db.db_schemas import CallRecord, OutboundCallQueue, OutboundSIP
from src.core.logger import logger
from src.services.livekit.livekit_svc import LiveKitService

# Queue items stuck in 'dispatching' longer than this indicate a worker crash
# mid-dispatch. Reset them back to 'pending' (or 'failed' past MAX_RETRIES).
STUCK_DISPATCHING_MINUTES = 5

MAX_RETRIES = 3           # permanent failure after this many attempts

livekit_services = LiveKitService()

_new_call_event = asyncio.Event()

# In-memory reservation counter: tracks calls that are mid-dispatch
# (room created but CallRecord not yet written). Prevents double-dispatch.
_dispatching_count = 0


async def _fail_all_active_calls() -> None:
    """On startup, immediately fail every initiated/answered call record.

    These calls belong to agent processes that died with the previous server
    instance. They will never complete, so fail them now to free concurrency slots.
    """
    now = datetime.now(timezone.utc)
    stale = await CallRecord.find(
        In(CallRecord.call_status, ["initiated", "answered"]),
    ).to_list()
    if stale:
        for record in stale:
            record.call_status = "failed"
            record.call_status_reason = "Marked failed on server startup — agent process no longer running"
            record.ended_at = now
            await record.save()
        logger.warning(
            f"Startup cleanup: marked {len(stale)} call record(s) as failed"
        )


async def _recover_stuck_dispatching() -> None:
    """Recover queue items left in 'dispatching' by a crashed worker.

    Runs on every dispatcher tick. Resets them to 'pending' so they retry,
    or 'failed' once MAX_RETRIES is reached.
    """
    queue_cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_DISPATCHING_MINUTES)
    stuck = await OutboundCallQueue.find(
        OutboundCallQueue.status == "dispatching",
        OutboundCallQueue.queued_at < queue_cutoff,
    ).to_list()
    if stuck:
        for item in stuck:
            item.retry_count += 1
            item.last_error = "Worker crashed mid-dispatch"
            if item.retry_count >= MAX_RETRIES:
                item.status = "failed"
            else:
                item.status = "pending"
            await item.save()
        logger.warning(
            f"Cleanup: recovered {len(stuck)} stuck 'dispatching' queue item(s)"
        )


async def _get_active_session_count() -> int:
    """Count calls that are live (initiated/answered) PLUS any mid-dispatch reservations."""
    db_active = await CallRecord.find(
        In(CallRecord.call_status, ["initiated", "answered"])
    ).count()
    return db_active + _dispatching_count


async def try_reserve_slot() -> bool:
    """Atomically reserve a session slot if one is free. Returns True on success."""
    global _dispatching_count
    if await _get_active_session_count() >= settings.MAX_CONCURRENT_JOBS:
        return False
    _dispatching_count += 1
    return True


def release_slot() -> None:
    """Release a reservation taken by try_reserve_slot()."""
    global _dispatching_count
    if _dispatching_count > 0:
        _dispatching_count -= 1


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
    _dispatching_count += 1  # reserve slot immediately (released in finally via release_slot)
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
                queue_id=item.queue_id,
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
                queue_id=item.queue_id,
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
        item.room_name = room_name
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
        release_slot()  # release reservation taken at top of this function


async def _process_pending() -> None:
    """Check queue and dispatch as many calls as current capacity allows."""
    try:
        active = await _get_active_session_count()
        slots = settings.MAX_CONCURRENT_JOBS - active

        if slots <= 0:
            logger.info(f"Dispatcher: active={active}, no slots available (max={settings.MAX_CONCURRENT_JOBS})")
            return

        pending = (
            await OutboundCallQueue.find(OutboundCallQueue.status == "pending")
            .sort("queued_at")
            .limit(slots)
            .to_list()
        )

        if not pending:
            logger.debug(f"Dispatcher: active={active}, slots={slots}, queue empty")
            return

        for item in pending:
            item.status = "dispatching"
            await item.save()
            asyncio.create_task(_dispatch_queued_call(item))

        logger.info(
            f"Dispatcher: active={active}, slots={slots}, "
            f"dispatching {len(pending)} call(s)"
        )
    except Exception as e:
        logger.error(f"Dispatcher process error: {e}", exc_info=True)


_TERMINAL_STATUSES = [
    "completed", "failed", "busy", "no_answer",
    "rejected", "cancelled", "unreachable", "timeout",
]


async def _watch_for_new_calls() -> None:
    """Change Stream: wakes dispatcher the moment a new call is inserted — cross-container."""
    while True:
        try:
            col = Database.client[settings.DATABASE_NAME]["outbound_call_queue"]
            async with await col.watch([{"$match": {"operationType": "insert"}}]) as stream:
                async for _ in stream:
                    logger.info("ChangeStream: new call queued → waking dispatcher")
                    _new_call_event.set()
        except Exception as e:
            logger.warning(f"ChangeStream (new calls) error, restarting in 5s: {e}")
            await asyncio.sleep(5)


async def _watch_for_call_completions() -> None:
    """Change Stream: wakes dispatcher when a call finishes → chain next pending call."""
    pipeline = [{
        "$match": {
            "operationType": "update",
            "updateDescription.updatedFields.call_status": {"$in": _TERMINAL_STATUSES},
        }
    }]
    while True:
        try:
            col = Database.client[settings.DATABASE_NAME]["call_records"]
            async with await col.watch(pipeline) as stream:
                async for _ in stream:
                    logger.info("ChangeStream: call completed → checking pending queue")
                    _new_call_event.set()
        except Exception as e:
            logger.warning(f"ChangeStream (completions) error, restarting in 5s: {e}")
            await asyncio.sleep(5)


async def outbound_dispatcher_loop() -> None:
    """Event-driven dispatcher: wakes instantly when a call is enqueued or completes.

    Change Streams provide cross-container notification. 30s poll is a safety-net fallback.
    """
    logger.info(f"Outbound call dispatcher started (max_concurrent={settings.MAX_CONCURRENT_JOBS})")

    await _fail_all_active_calls()
    await _process_pending()

    asyncio.create_task(_watch_for_new_calls())
    asyncio.create_task(_watch_for_call_completions())

    while True:
        try:
            await asyncio.wait_for(_new_call_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass  # safety-net poll
        finally:
            _new_call_event.clear()

        # Check for stuck dispatching
        await _recover_stuck_dispatching()
        await _process_pending()
