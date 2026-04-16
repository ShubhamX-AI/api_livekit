from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.responses import JSONResponse
from src.api.models.api_schemas import TriggerOutboundCall
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import OutboundSIP, APIKey, Assistant, OutboundCallQueue
from src.api.dependencies import get_current_user
from src.core.logger import logger, setup_logging
from src.services.outbound_dispatcher import notify_dispatcher

router = APIRouter()
setup_logging()


@router.post("/outbound", status_code=202)
async def trigger_outbound_call(
    request: TriggerOutboundCall, current_user: APIKey = Depends(get_current_user)
):
    logger.info(
        f"Received outbound call request | user={current_user.user_email} "
        f"service={request.call_service} to={request.to_number}"
    )

    assistant = await Assistant.find_one(
        Assistant.assistant_id == request.assistant_id,
        Assistant.assistant_created_by_email == current_user.user_email,
    )
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found in DB")

    trunk = await OutboundSIP.find_one(
        OutboundSIP.trunk_id == request.trunk_id,
        OutboundSIP.trunk_created_by_email == current_user.user_email,
        OutboundSIP.trunk_is_active == True,
    )
    if not trunk:
        raise HTTPException(status_code=404, detail="Trunk not found in DB")

    queue_item = OutboundCallQueue(
        user_email=current_user.user_email,
        assistant_id=assistant.assistant_id,
        assistant_name=assistant.assistant_name,
        trunk_id=trunk.trunk_id,
        to_number=request.to_number,
        call_service=request.call_service,
        job_metadata=request.metadata or {},
    )
    await queue_item.insert()
    notify_dispatcher()  # wake dispatcher immediately — no 60s wait

    logger.info(
        f"Enqueued outbound call {queue_item.queue_id} | "
        f"to={request.to_number} user={current_user.user_email}"
    )

    return JSONResponse(
        status_code=202,
        content=apiResponse(
            success=True,
            message="Outbound call queued successfully",
            data={"queue_id": queue_item.queue_id, "status": "queued"},
        ).model_dump(),
    )


@router.get("/queue/{queue_id}")
async def get_queue_status(
    queue_id: str, current_user: APIKey = Depends(get_current_user)
):
    item = await OutboundCallQueue.find_one(
        OutboundCallQueue.queue_id == queue_id,
        OutboundCallQueue.user_email == current_user.user_email,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    return apiResponse(
        success=True,
        message="Queue status retrieved",
        data={
            "queue_id": item.queue_id,
            "status": item.status,
            "to_number": item.to_number,
            "call_service": item.call_service,
            "queued_at": item.queued_at.isoformat(),
            "dispatched_at": item.dispatched_at.isoformat() if item.dispatched_at else None,
            "retry_count": item.retry_count,
            "last_error": item.last_error,
        },
    )


@router.post("/end_call")
async def end_call(request: Request, _: dict = Body(...)):
    logger.info("Received payload after end call")
    body = await request.json()
    return apiResponse(
        success=True,
        message="Call ended successfully",
        data=body,
    )
