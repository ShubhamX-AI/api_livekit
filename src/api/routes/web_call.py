from fastapi import APIRouter, HTTPException, Depends
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import Assistant, APIKey
from src.api.dependencies import get_current_user
from src.core.logger import logger, setup_logging
from src.services.livekit.livekit_svc import LiveKitService
from src.api.models.api_schemas import TriggerWebCall

router = APIRouter()
setup_logging()
livekit_services = LiveKitService()

# Generate Web Call Token
@router.post("/getToken")
async def get_token(request: TriggerWebCall, current_user: APIKey = Depends(get_current_user)):
    try:
        logger.info(f"Web call token requested by: {current_user.user_email} for assistant: {request.assistant_id}")

        # Verify the assistant belongs to this user
        assistant = await Assistant.find_one(
            Assistant.assistant_id == request.assistant_id,
            Assistant.assistant_created_by_email == current_user.user_email,
        )
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Create a unique room
        logger.info(f"Creating room for assistant: {request.assistant_id}")
        room_name = await livekit_services.create_room(request.assistant_id)

        # Generate join token (agent dispatch embedded via RoomConfiguration)
        logger.info(f"Creating token for room: {room_name}")
        token = await livekit_services.create_token(room_name, request.metadata)
        if not token:
            raise HTTPException(status_code=500, detail="Failed to generate token")

        return apiResponse(
            success=True,
            message="Token generated successfully",
            data={
                "room_name": room_name,
                "token": token,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating web call token: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))