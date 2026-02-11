from fastapi import APIRouter, HTTPException
from src.api.models.api_schemas import CreateApiKeyRequest
from src.api.models.response_models import apiResponse
from src.core.models.db_schemas import APIKey
import uuid

router = APIRouter()

@router.post("/create-api-key")
async def create_api_key(request: CreateApiKeyRequest):
    try:
        # check if user already exists
        existing_user = await APIKey.find_one(APIKey.user_email == request.user_email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # generate api key
        api_key = "lvk_vyom_" + str(uuid.uuid4())

        # create new user
        user = APIKey(user_name=request.user_name,org_name=request.org_name,user_email=request.user_email,api_key=api_key)
        await user.insert()
        
        return apiResponse(
            success=True,
            message="API key created successfully, Store it securely",
            data={
                "api_key": api_key,
                "user_name": request.user_name,
                "org_name": request.org_name,
                "user_email": request.user_email
            }
        )
    except Exception as e:
        return apiResponse(
            success=False,
            message=str(e),
            data={}
        )
