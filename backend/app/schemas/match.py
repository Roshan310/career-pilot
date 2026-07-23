import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MatchCreateRequest(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class MatchStatusResponse(BaseModel):
    id: uuid.UUID
    status: str


class MatchResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    error_message: str | None
    overall_score: float | None
    semantic_score: float | None
    skill_overlap_score: float | None
    experience_match_score: float | None
    keyword_density_score: float | None
    matched_skills: list | None
    missing_skills: list | None
    suggestions: list | None
    ats_issues: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestionsResponse(BaseModel):
    suggestions: list = Field(default_factory=list)
