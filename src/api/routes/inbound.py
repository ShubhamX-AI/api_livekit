from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user
from src.api.models.api_schemas import AssignInboundNumber, UpdateInboundMapping
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import APIKey, Assistant, InboundSIP
from src.core.logger import logger, setup_logging
from src.services.exotel.custom_sip_reach.sip_client import format_exotel_number

router = APIRouter()
setup_logging()


def normalize_inbound_number(phone_number: str) -> str:
    return format_exotel_number(phone_number)


async def get_user_assistant(assistant_id: str, user_email: str) -> Assistant:
    assistant = await Assistant.find_one(
        Assistant.assistant_id == assistant_id,
        Assistant.assistant_created_by_email == user_email,
        Assistant.assistant_is_active == True,
    )
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant


async def get_user_inbound_mapping(inbound_id: str, user_email: str) -> InboundSIP:
    inbound_mapping = await InboundSIP.find_one(
        InboundSIP.inbound_id == inbound_id,
        InboundSIP.created_by_email == user_email,
        InboundSIP.is_active == True,
    )
    if not inbound_mapping:
        raise HTTPException(status_code=404, detail="Inbound number mapping not found")
    return inbound_mapping


@router.post("/assign")
async def assign_inbound_number(
    request: AssignInboundNumber, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Assigning inbound number for user: {current_user.user_email}")

    if request.service != "exotel":
        raise HTTPException(
            status_code=400,
            detail=f"Inbound via {request.service} is not supported yet",
        )

    await get_user_assistant(request.assistant_id, current_user.user_email)
    
    actual_phone = request.inbound_config.phone_number
    normalized_number = normalize_inbound_number(actual_phone)
    if len(normalized_number) < 10:
        raise HTTPException(status_code=400, detail="Invalid inbound phone number")

    existing_mapping = await InboundSIP.find_one(
        InboundSIP.phone_number_normalized == normalized_number,
        InboundSIP.is_active == True,
    )
    if existing_mapping:
        raise HTTPException(status_code=409, detail="Inbound number already assigned")

    inbound_mapping = InboundSIP(
        inbound_id=str(uuid.uuid4()),
        phone_number=actual_phone,
        phone_number_normalized=normalized_number,
        inbound_config=request.inbound_config.model_dump(),
        assistant_id=request.assistant_id,
        service=request.service,
        created_by_email=current_user.user_email,
        updated_by_email=current_user.user_email,
    )
    await inbound_mapping.insert()

    return apiResponse(
        success=True,
        message="Inbound number assigned successfully",
        data={
            "inbound_id": inbound_mapping.inbound_id,
            "phone_number": inbound_mapping.phone_number,
            "phone_number_normalized": inbound_mapping.phone_number_normalized,
            "assistant_id": inbound_mapping.assistant_id,
            "service": inbound_mapping.service,
            "inbound_config": inbound_mapping.inbound_config,
        },
    )


@router.patch("/update/{inbound_id}")
async def update_inbound_mapping(
    inbound_id: str,
    request: UpdateInboundMapping,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Updating inbound mapping: {inbound_id}")

    inbound_mapping = await get_user_inbound_mapping(
        inbound_id, current_user.user_email
    )
    await get_user_assistant(request.assistant_id, current_user.user_email)

    inbound_mapping.assistant_id = request.assistant_id
    inbound_mapping.updated_at = datetime.now(timezone.utc)
    inbound_mapping.updated_by_email = current_user.user_email
    await inbound_mapping.save()

    return apiResponse(
        success=True,
        message="Inbound number mapping updated successfully",
        data={
            "inbound_id": inbound_mapping.inbound_id,
            "assistant_id": inbound_mapping.assistant_id,
        },
    )


@router.post("/detach/{inbound_id}")
async def detach_inbound_number(
    inbound_id: str, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Detaching inbound mapping: {inbound_id}")

    inbound_mapping = await get_user_inbound_mapping(
        inbound_id, current_user.user_email
    )
    inbound_mapping.assistant_id = None
    inbound_mapping.updated_at = datetime.now(timezone.utc)
    inbound_mapping.updated_by_email = current_user.user_email
    await inbound_mapping.save()

    return apiResponse(
        success=True,
        message="Inbound number detached successfully",
        data={
            "inbound_id": inbound_mapping.inbound_id,
            "assistant_id": inbound_mapping.assistant_id,
        },
    )


@router.delete("/delete/{inbound_id}")
async def delete_inbound_number(
    inbound_id: str, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Deleting inbound mapping: {inbound_id}")

    inbound_mapping = await get_user_inbound_mapping(
        inbound_id, current_user.user_email
    )
    inbound_mapping.is_active = False
    inbound_mapping.assistant_id = None
    inbound_mapping.updated_at = datetime.now(timezone.utc)
    inbound_mapping.updated_by_email = current_user.user_email
    await inbound_mapping.save()

    return apiResponse(
        success=True,
        message="Inbound number deleted successfully",
        data={"inbound_id": inbound_mapping.inbound_id},
    )


@router.get("/list")
async def list_inbound_numbers(current_user: APIKey = Depends(get_current_user)):
    logger.info(f"Listing inbound mappings for user: {current_user.user_email}")

    inbound_mappings = (
        await InboundSIP.find(
            InboundSIP.created_by_email == current_user.user_email,
            InboundSIP.is_active == True,
        )
        .sort("-created_at")
        .to_list()
    )

    data = []
    for inbound_mapping in inbound_mappings:
        assistant_name = None
        if inbound_mapping.assistant_id:
            assistant = await Assistant.find_one(
                Assistant.assistant_id == inbound_mapping.assistant_id,
                Assistant.assistant_created_by_email == current_user.user_email,
                Assistant.assistant_is_active == True,
            )
            if assistant:
                assistant_name = assistant.assistant_name

        data.append(
            {
                "inbound_id": inbound_mapping.inbound_id,
                "phone_number": inbound_mapping.phone_number,
                "phone_number_normalized": inbound_mapping.phone_number_normalized,
                "inbound_config": inbound_mapping.inbound_config,
                "assistant_id": inbound_mapping.assistant_id,
                "assistant_name": assistant_name,
                "service": inbound_mapping.service,
                "created_at": inbound_mapping.created_at,
                "updated_at": inbound_mapping.updated_at,
            }
        )

    return apiResponse(
        success=True,
        message="Inbound numbers retrieved successfully",
        data=data,
    )
