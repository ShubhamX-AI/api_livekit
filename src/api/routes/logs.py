from typing import Optional
from fastapi import APIRouter, Depends
from src.api.dependencies import get_current_user
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import APIKey, ActivityLog

router = APIRouter()


@router.get("")
async def get_activity_logs(
    log_type: Optional[str] = None,      # filter by "tool_call" or "end_call_webhook"
    assistant_id: Optional[str] = None,  # filter to a specific assistant
    room_name: Optional[str] = None,     # filter to a specific call
    page: int = 1,
    limit: int = 50,
    current_user: APIKey = Depends(get_current_user),
):
    """Return paginated activity logs scoped to the authenticated user."""
    limit = min(limit, 100)  # cap at 100 per page
    skip = (page - 1) * limit

    # Base filter — always scope to requesting user
    filters = {"user_email": current_user.user_email}
    if log_type:
        filters["log_type"] = log_type
    if assistant_id:
        filters["assistant_id"] = assistant_id
    if room_name:
        filters["room_name"] = room_name

    query = ActivityLog.find(filters)
    total = await query.count()
    logs = await query.sort(-ActivityLog.timestamp).skip(skip).limit(limit).to_list()

    # Serialize — exclude internal Beanie _id
    log_list = []
    for log in logs:
        entry = log.model_dump(exclude={"id"})
        log_list.append(entry)

    return apiResponse(
        success=True,
        message="Activity logs fetched successfully",
        data={
            "logs": log_list,
            "total": total,
            "page": page,
            "limit": limit,
        },
    )
