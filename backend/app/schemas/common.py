from datetime import datetime

from pydantic import BaseModel


class UsageResponse(BaseModel):
    monthly_match_count: int
    monthly_match_limit: int
    monthly_interview_count: int
    monthly_interview_limit: int
    usage_reset_at: datetime | None
