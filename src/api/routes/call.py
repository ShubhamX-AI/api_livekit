from fastapi import APIRouter, HTTPException, Depends, Request, Body
from src.api.models.api_schemas import TriggerOutboundCall
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import OutboundSIP, APIKey, Assistant
from src.api.dependencies import get_current_user
from src.core.logger import logger, setup_logging
from src.services.livekit.livekit_svc import LiveKitService
from google.protobuf.json_format import MessageToDict
import uuid
import json

router = APIRouter()
setup_logging()
livekit_services = LiveKitService()


# Triggure Ouboud call
@router.post("/outbound")
async def trigger_outbound_call(
    request: TriggerOutboundCall, current_user: APIKey = Depends(get_current_user)
):
    logger.info(
        f"Received request to trigger outbound call for user: {current_user.user_email} service: {request.call_service}"
    )

    # Check of the assistant exists for the user
    assistant = await Assistant.find_one(
        Assistant.assistant_id == request.assistant_id,
        Assistant.assistant_created_by_email == current_user.user_email,
    )
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found in DB")

    # Check of the trunk exists for the user
    trunk = await OutboundSIP.find_one(
        OutboundSIP.trunk_id == request.trunk_id,
        OutboundSIP.trunk_created_by_email == current_user.user_email,
    )
    if not trunk:
        raise HTTPException(status_code=404, detail="Trunk not found in DB")

    # Create room (unique room name with assistant name) common for all the call services
    logger.info(f"Creating room for assistant: {request.assistant_id}")
    room_name = await livekit_services.create_room(request.assistant_id)

    # Job metadata common for all the call services
    job_metadata = request.metadata or {}
    job_metadata["to_number"] = request.to_number

    # Create agent dispatch common for all the call services
    logger.info(f"Creating dispatch for room: {room_name}")
    agent_dispatch = await livekit_services.create_agent_dispatch(room_name, job_metadata)

    if request.call_service == "twilio":
        # Create SIP participant
        logger.info(f"Triggering Twilio SIP participant for number: {request.to_number}")
        participant = await livekit_services.create_sip_participant(
            room_name=room_name,
            to_number=request.to_number,
            trunk_id=request.trunk_id,
            participant_identity=uuid.uuid4().hex,
        )

        return apiResponse(
            success=True,
            message="Outbound call triggered successfully via Twilio",
            data={
                "room_name": room_name,
                "agent_dispatch": MessageToDict(agent_dispatch),
                "participant": MessageToDict(participant),
            },
        )

    elif request.call_service == "exotel":
        # Custom SIP bridge for Exotel
        from src.services.exotel.custom_sip_reach.bridge import run_bridge

        logger.info(f"Triggering Exotel SIP bridge call to {request.to_number}")

        # Trunk config (Exotel number, etc.)
        sip_config = trunk.trunk_config

        # Run bridge in background
        logger.info(f"Starting SIP bridge background task")
        import asyncio

        # We don't await this, just fire and forget (the bridge handles its own lifecycle)
        asyncio.create_task(
            run_bridge(
                phone_number=request.to_number,
                room_name=room_name,
                sip_config=sip_config,
            )
        )

        return apiResponse(
            success=True,
            message="Outbound call triggered successfully via Exotel bridge",
            data={
                "room_name": room_name,
                "agent_dispatch": MessageToDict(agent_dispatch),
            },
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Call service '{request.call_service}' not supported",
        )


# DEMO END CALL URL endpoint. This endpint will be hit after the call is ended
@router.post("/end_call")
async def end_call(request: Request, _ : dict= Body(...)):
    
    logger.info(f"Received payload after end call")
    
    # Get the request body
    body = await request.json()
    
    # Get the room name from the body
    return apiResponse(
        success=True,
        message="Call ended successfully",
        data=body,
    )