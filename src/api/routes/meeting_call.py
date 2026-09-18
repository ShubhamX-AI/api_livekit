"""Meeting calls: dispatch an assistant and a browser connector into one LiveKit room."""

from fastapi import APIRouter, Depends, HTTPException
from google.protobuf.json_format import MessageToDict

from src.api.dependencies import get_current_user
from src.api.models.api_schemas import TriggerMeetingCall
from src.api.models.response_models import apiResponse
from src.core.call_types import CALL_TYPE_MEETING
from src.core.config import settings
from src.core.db.db_schemas import APIKey, Assistant, CallRecord
from src.core.logger import logger
from src.services.livekit.livekit_svc import LiveKitService
from src.services.meeting_connector import (
    UnsupportedMeetingPlatform,
    validate_meeting_url,
)
from src.services.outbound_dispatcher.dispatcher import (
    MEETING,
    release_slot,
    try_reserve_slot,
)

router = APIRouter()
livekit_services = LiveKitService()


@router.post("/join")
async def join_meeting(request: TriggerMeetingCall, current_user: APIKey = Depends(get_current_user)):
    slot_held = False
    room_name = None
    try:
        logger.info(
            f"Meeting call requested by: {current_user.user_email} for assistant: {request.assistant_id} "
            f"on platform: {request.platform}"
        )

        assistant = await Assistant.find_one(
            Assistant.assistant_id == request.assistant_id,
            Assistant.assistant_created_by_email == current_user.user_email,
        )
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Cheap rejections first, before anything is reserved or created. A malformed URL
        # otherwise reaches a worker that cannot join, after holding a capacity slot.
        try:
            validate_meeting_url(request.platform, request.meeting_url)
        except UnsupportedMeetingPlatform as e:
            # A platform accepted by the schema but lacking a URL pattern is a deployment gap,
            # not a bad request. Answering 400 here would blame the caller for it.
            logger.error(f"Meeting platform '{request.platform}' is not fully configured: {e}")
            raise HTTPException(status_code=503, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Meeting calls get their own bucket because the connector's browser is far more
        # expensive than either a web call or a phone call.
        if not await try_reserve_slot(MEETING):
            logger.warning("Meeting call rejected — concurrency cap reached")
            raise HTTPException(status_code=503, detail="Server at capacity, please retry shortly")
        slot_held = True

        logger.info(f"Creating room for assistant: {request.assistant_id}")
        room_name = await livekit_services.create_room(request.assistant_id)

        job_metadata = {
            **(request.metadata or {}),
            "call_type": CALL_TYPE_MEETING,
            "meeting_platform": request.platform,
            "meeting_url": request.meeting_url,
        }

        await livekit_services.initialize_call_record(
            room_name=room_name,
            assistant_id=assistant.assistant_id,
            assistant_name=assistant.assistant_name,
            to_number=request.meeting_url,
            call_status="initiated",
            created_by_email=current_user.user_email,
            call_type=CALL_TYPE_MEETING,
            call_service=request.platform,
        )
        # Reservation handed over to the DB-counted CallRecord above.
        release_slot(MEETING)
        slot_held = False

        logger.info(f"Creating dispatch for room: {room_name}")
        agent_dispatch = await livekit_services.create_agent_dispatch(room_name, job_metadata)

        await CallRecord.find_one(CallRecord.room_name == room_name).update(
            {
                "$set": {
                    "meeting_url": request.meeting_url,
                    "meeting_connector_status": "pending",
                }
            }
        )

        connector_metadata = {
            "call_type": CALL_TYPE_MEETING,
            "platform": request.platform,
            "meeting_url": request.meeting_url,
            "bot_display_name": request.bot_display_name or assistant.assistant_name or "Assistant",
        }
        logger.info(f"Creating connector dispatch for room: {room_name}")
        connector_dispatch = await livekit_services.create_agent_dispatch(
            room_name,
            connector_metadata,
            agent_name=settings.MEETING_CONNECTOR_AGENT_NAME,
        )

        return apiResponse(
            success=True,
            message="Meeting call started successfully",
            data={
                "room_name": room_name,
                "platform": request.platform,
                "meeting_url": request.meeting_url,
                "agent_dispatch": MessageToDict(agent_dispatch),
                "connector_dispatch": MessageToDict(connector_dispatch),
            },
        )

    except HTTPException:
        # The room only exists once we got past reservation, and an HTTPException raised after
        # that point would otherwise leave a room with an idle agent billing against the cap.
        await _abandon_room(room_name)
        raise
    except Exception as e:
        logger.error(f"Error starting meeting call: {e!s}", exc_info=True)
        await _abandon_room(room_name)
        raise HTTPException(status_code=500, detail="Failed to start meeting call") from e
    finally:
        # Releases the reservation if we bailed out before the CallRecord took over counting it.
        if slot_held:
            release_slot(MEETING)


async def _abandon_room(room_name: str | None) -> None:
    """End a room we created but could not finish setting up.

    Without this, a failed connector dispatch leaves a LiveKit room with an agent sitting in it,
    counted against MAX_CONCURRENT_MEETING_CALLS until the worker's own timeout fires.
    """
    if not room_name:
        return
    try:
        await livekit_services.update_call_status(
            room_name,
            "failed",
            call_status_reason="Meeting call setup failed",
        )
    except Exception as e:
        logger.warning(f"Failed to mark abandoned meeting call {room_name}: {e}")
    try:
        await livekit_services.end_call(room_name)
    except Exception as e:
        logger.warning(f"Failed to clean up room {room_name} after a failed meeting call: {e}")
    try:
        await livekit_services.delete_room(room_name)
    except Exception as e:
        logger.warning(f"Failed to delete abandoned meeting room {room_name}: {e}")
