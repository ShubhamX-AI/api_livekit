from fastapi import APIRouter
from src.api.models.api_schemas import CreateApiKeyRequest
from src.api.models.response_models import apiResponse


router = APIRouter()

@router.post("/create-api-key")
def create_api_key(request: CreateApiKeyRequest):
    try:
        return apiResponse(
            success=True,
            message="API key created successfully",
            data=request.model_dump()
        )
    except Exception as e:
        return apiResponse(
            success=False,
            message="API key creation failed",
            data={}
        )
