from fastapi import APIRouter, HTTPException, Depends
from src.api.models.api_schemas import CreateAssistant, UpdateAssistant
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import Assistant, APIKey
from src.api.dependencies import get_current_user
from src.core.logger import logger, setup_logging
import uuid
from datetime import datetime

router = APIRouter()
setup_logging()


def mask_api_key(tts_config: dict) -> dict:
    """Mask the API key in the TTS config for security."""
    if not tts_config:
        return tts_config
    
    masked_config = tts_config.copy()
    if "api_key" in masked_config and masked_config["api_key"]:
        key = masked_config["api_key"]
        if len(key) > 8:
            masked_config["api_key"] = f"{key[:4]}...{key[-4:]}"
        else:
            masked_config["api_key"] = "****"
    else:
        masked_config["api_key"] = "Using System provided API Key"
    return masked_config


# Create new assistant
@router.post("/create")
async def create_assistant(
    request: CreateAssistant, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Received request to create assistant")
    # Generate unique assistant ID
    assistant_id = str(uuid.uuid4())

    # Convert Pydantic model to dict
    assistant_data = request.model_dump()

    try:
        logger.info(f"Inserting assistant into database")
        # Create database document
        new_assistant = Assistant(
            assistant_id=assistant_id,
            assistant_created_by_email=current_user.user_email,
            assistant_updated_by_email=current_user.user_email,
            **assistant_data,
        )
        await new_assistant.insert()
    except Exception as e:
        logger.error(f"Failed to create assistant: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to create assistant: {e}")

    logger.info(f"Assistant created successfully: {assistant_id}")
    return apiResponse(
        success=True,
        message="Assistant created successfully",
        data={
            "assistant_id": assistant_id,
            "assistant_name": new_assistant.assistant_name,
        },
    )


# Update assistant
@router.patch("/update/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    request: UpdateAssistant,
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Received request to update assistant: {assistant_id}")


    # Update fields
    update_data = request.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    logger.info(f"Updating assistant {assistant_id}")
    update_data.update(
        {
            "assistant_updated_at": datetime.utcnow(),
            "assistant_updated_by_email": current_user.user_email,
        }
    )

    result = await Assistant.find_one(
        Assistant.assistant_id == assistant_id,
        Assistant.assistant_created_by_email == current_user.user_email,
    ).update({"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Assistant not found")

    logger.info(f"Assistant updated successfully: {assistant_id}")
    return apiResponse(
        success=True,
        message="Assistant updated successfully",
        data={"assistant_id": assistant_id},
    )


# List assistants
@router.get("/list")
async def list_assistants(current_user: APIKey = Depends(get_current_user)):
    logger.info(f"Received request to list assistants")

    # Fetch only active assistants created by the current user
    assistants = await Assistant.find(
        Assistant.assistant_created_by_email == current_user.user_email,
        Assistant.assistant_is_active == True,
    ).to_list()

    # Filter only requested fields
    filtered_assistants = [
        {
            "assistant_id": assistant.assistant_id,
            "assistant_name": assistant.assistant_name,
            "assistant_tts_model": assistant.assistant_tts_model,
            "assistant_tts_config": mask_api_key(assistant.assistant_tts_config),
            "assistant_created_by_email": assistant.assistant_created_by_email,
        }
        for assistant in assistants
    ]

    return apiResponse(
        success=True,
        message="Assistants retrieved successfully",
        data=filtered_assistants,
    )


# Fetch assistant details
@router.get("/details/{assistant_id}")
async def get_assistant_details(
    assistant_id: str, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Received request to get assistant details: {assistant_id}")

    assistant = await Assistant.find_one(
        Assistant.assistant_id == assistant_id,
        Assistant.assistant_created_by_email == current_user.user_email,
        Assistant.assistant_is_active == True,
    )

    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    assistant_data = assistant.model_dump(exclude={"id"})
    assistant_data["assistant_tts_config"] = mask_api_key(assistant_data.get("assistant_tts_config", {}))

    return apiResponse(
        success=True,
        message="Assistant details retrieved successfully",
        data=assistant_data,
    )


# Delete assistant
@router.delete("/delete/{assistant_id}")
async def delete_assistant(
    assistant_id: str, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Received request to delete assistant: {assistant_id}")

    assistant = await Assistant.find_one(
        Assistant.assistant_id == assistant_id,
        Assistant.assistant_created_by_email == current_user.user_email,
        Assistant.assistant_is_active == True,
    )

    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    assistant.assistant_is_active = False
    assistant.assistant_updated_at = datetime.utcnow()
    assistant.assistant_updated_by_email = current_user.user_email
    await assistant.save()

    logger.info(f"Assistant deleted successfully: {assistant_id}")
    return apiResponse(
        success=True,
        message="Assistant deleted successfully",
        data={"assistant_id": assistant_id},
    )
