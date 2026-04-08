import math
from typing import Optional


NON_BILLABLE_FINAL_STATUSES = {
    "busy",
    "no_answer",
    "rejected",
    "cancelled",
    "unreachable",
    "timeout",
    "failed",
}


def calculate_billable_duration_minutes(
    call_status: str,
    call_duration_minutes: Optional[float],
) -> Optional[int]:
    """Return billable minutes using the platform billing rule."""
    if call_status in NON_BILLABLE_FINAL_STATUSES:
        return 0
    if call_duration_minutes is None:
        return None
    if call_duration_minutes <= 0:
        return 0
    return math.ceil(call_duration_minutes)
