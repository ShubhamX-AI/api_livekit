from fastapi import APIRouter
from src.api.models.response_models import apiResponse

router = APIRouter()


@router.get("/health")
async def health():
    return apiResponse(success=True, message="Service is healthy and operational", data={})
