from fastapi import APIRouter, HTTPException, Depends
from src.api.models.api_schemas import CreateOutboundTrunk
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import OutboundSIP, APIKey
from src.api.dependencies import get_current_user
from src.core.logger import logger, setup_logging
from src.services.livekit.livekit_svc import LiveKitService
from google.protobuf.json_format import MessageToDict
import uuid

router = APIRouter()
setup_logging()
livekit_services = LiveKitService()


# Create Outbound Trunk
@router.post("/create-outbound-trunk")
async def create_outbound_trunk(
    request: CreateOutboundTrunk, current_user: APIKey = Depends(get_current_user)
):
    logger.info(f"Received request to create outbound trunk of type: {request.trunk_type}")
    try:
        trunk_id = None
        trunk_config_to_save = {}

        if request.trunk_type == "twilio":
            # Creating outbound trunk in LiveKit
            try:
                # We expect TwilioTrunkConfig here
                config = request.trunk_config
                trunk = await livekit_services.create_sip_outbound_trunk(
                    trunk_name=request.trunk_name,
                    trunk_address=config.address,
                    trunk_numbers=config.numbers,
                    trunk_auth_username=config.username,
                    trunk_auth_password=config.password,
                )
                trunk_dict = MessageToDict(trunk)
                trunk_id = trunk_dict["sipTrunkId"]
                trunk_config_to_save = config.model_dump()
            except Exception as e:
                logger.error(f"Failed to create outbound trunk in LiveKit: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create outbound trunk in LiveKit: {str(e)}",
                )
        elif request.trunk_type == "exotel":
            # Local Exotel trunk, just generate a trunk_id
            trunk_id = f"exotel_{uuid.uuid4().hex[:8]}"
            trunk_config_to_save = request.trunk_config.model_dump()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Trunk type '{request.trunk_type}' not supported.",
            )

        logger.info(f"Inserting outbound trunk into database: {trunk_id}")
        outbound_trunk = OutboundSIP(
            trunk_id=trunk_id,
            trunk_name=request.trunk_name,
            trunk_type=request.trunk_type,
            trunk_config=trunk_config_to_save,
            trunk_created_by_email=current_user.user_email,
            trunk_updated_by_email=current_user.user_email,
        )
        await outbound_trunk.insert()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create/insert outbound trunk: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create outbound trunk: {str(e)}",
        )

    logger.info(f"Outbound trunk created successfully: {trunk_id}")
    return apiResponse(
        success=True,
        message="Outbound trunk created successfully, Store the trunk id securely.",
        data={"trunk_id": trunk_id},
    )


# List SIP trunks
@router.get("/list")
async def list_sip_trunks(current_user: APIKey = Depends(get_current_user)):
    logger.info(f"Received request to list SIP trunks")

    # Fetch only active trunks created by the current user
    trunks = await OutboundSIP.find(
        OutboundSIP.trunk_created_by_email == current_user.user_email,
        OutboundSIP.trunk_is_active == True,
    ).to_list()

    # Filter only requested fields
    filtered_trunks = [
        {
            "trunk_id": trunk.trunk_id,
            "trunk_name": trunk.trunk_name,
            "trunk_created_by_email": trunk.trunk_created_by_email,
        }
        for trunk in trunks
    ]

    return apiResponse(
        success=True, message="SIP trunks retrieved successfully", data=filtered_trunks
    )
