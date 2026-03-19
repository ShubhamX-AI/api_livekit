from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user
from src.api.models.api_schemas import (
    CreateInboundContextStrategy,
    UpdateInboundContextStrategy,
)
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import (
    APIKey,
    InboundContextStrategy,
    InboundSIP,
)
from src.core.logger import logger, setup_logging

router = APIRouter()
setup_logging()


def mask_strategy_config(config: dict | None) -> dict | None:
    """Mask sensitive headers in webhook strategy configs."""
    if not config:
        return config

    masked_config = config.copy()
    headers = masked_config.get("headers")
    if isinstance(headers, dict):
        masked_headers = {}
        for key, value in headers.items():
            lowered_key = key.lower()
            if any(token in lowered_key for token in ("authorization", "token", "secret", "api-key", "apikey")) and value:
                masked_headers[key] = "****"
            else:
                masked_headers[key] = value
        masked_config["headers"] = masked_headers

    return masked_config


@router.post("/create")
async def create_inbound_context_strategy(
    request: CreateInboundContextStrategy,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Creating inbound context strategy for user: {current_user.user_email}")

    strategy_id = str(uuid.uuid4())
    strategy_data = request.model_dump()
    strategy_data["strategy_config"] = request.strategy_config.model_dump()

    try:
        strategy = InboundContextStrategy(
            strategy_id=strategy_id,
            strategy_created_by_email=current_user.user_email,
            strategy_updated_by_email=current_user.user_email,
            **strategy_data,
        )
        await strategy.insert()
    except Exception as exc:
        logger.error(f"Failed to create inbound context strategy: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create inbound context strategy: {exc}",
        )

    return apiResponse(
        success=True,
        message="Inbound context strategy created successfully",
        data={
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.strategy_name,
            "strategy_type": strategy.strategy_type,
        },
    )


@router.patch("/update/{strategy_id}")
async def update_inbound_context_strategy(
    strategy_id: str,
    request: UpdateInboundContextStrategy,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Updating inbound context strategy: {strategy_id}")

    strategy = await InboundContextStrategy.find_one(
        InboundContextStrategy.strategy_id == strategy_id,
        InboundContextStrategy.strategy_created_by_email == current_user.user_email,
        InboundContextStrategy.strategy_is_active == True,
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Inbound context strategy not found")

    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    if "strategy_config" in update_data and request.strategy_config is not None:
        merged_config = {
            **strategy.strategy_config,
            **request.strategy_config.model_dump(exclude_unset=True),
        }
        update_data["strategy_config"] = merged_config

    update_data.update(
        {
            "strategy_updated_at": datetime.now(timezone.utc),
            "strategy_updated_by_email": current_user.user_email,
        }
    )

    result = await InboundContextStrategy.find_one(
        InboundContextStrategy.strategy_id == strategy_id,
        InboundContextStrategy.strategy_created_by_email == current_user.user_email,
        InboundContextStrategy.strategy_is_active == True,
    ).update({"$set": update_data})

    return apiResponse(
        success=True,
        message="Inbound context strategy updated successfully",
        data={"strategy_id": strategy_id},
    )


@router.get("/list")
async def list_inbound_context_strategies(
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Listing inbound context strategies for user: {current_user.user_email}")

    strategies = await InboundContextStrategy.find(
        InboundContextStrategy.strategy_created_by_email == current_user.user_email,
        InboundContextStrategy.strategy_is_active == True,
    ).sort("-strategy_created_at").to_list()

    data = [
        {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.strategy_name,
            "strategy_type": strategy.strategy_type,
            "strategy_config": mask_strategy_config(strategy.strategy_config),
            "strategy_created_at": strategy.strategy_created_at,
            "strategy_updated_at": strategy.strategy_updated_at,
        }
        for strategy in strategies
    ]

    return apiResponse(
        success=True,
        message="Inbound context strategies retrieved successfully",
        data=data,
    )


@router.get("/details/{strategy_id}")
async def get_inbound_context_strategy_details(
    strategy_id: str,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Fetching inbound context strategy details: {strategy_id}")

    strategy = await InboundContextStrategy.find_one(
        InboundContextStrategy.strategy_id == strategy_id,
        InboundContextStrategy.strategy_created_by_email == current_user.user_email,
        InboundContextStrategy.strategy_is_active == True,
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Inbound context strategy not found")

    data = strategy.model_dump(exclude={"id"})
    data["strategy_config"] = mask_strategy_config(data.get("strategy_config"))

    return apiResponse(
        success=True,
        message="Inbound context strategy retrieved successfully",
        data=data,
    )


@router.delete("/delete/{strategy_id}")
async def delete_inbound_context_strategy(
    strategy_id: str,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Deleting inbound context strategy: {strategy_id}")

    strategy = await InboundContextStrategy.find_one(
        InboundContextStrategy.strategy_id == strategy_id,
        InboundContextStrategy.strategy_created_by_email == current_user.user_email,
        InboundContextStrategy.strategy_is_active == True,
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Inbound context strategy not found")

    strategy.strategy_is_active = False
    strategy.strategy_updated_at = datetime.now(timezone.utc)
    strategy.strategy_updated_by_email = current_user.user_email
    await strategy.save()

    mappings = await InboundSIP.find(
        InboundSIP.created_by_email == current_user.user_email,
        InboundSIP.inbound_context_strategy_id == strategy_id,
        InboundSIP.is_active == True,
    ).to_list()

    for mapping in mappings:
        mapping.inbound_context_strategy_id = None
        mapping.updated_at = datetime.now(timezone.utc)
        mapping.updated_by_email = current_user.user_email
        await mapping.save()

    return apiResponse(
        success=True,
        message="Inbound context strategy deleted successfully",
        data={"strategy_id": strategy_id},
    )
