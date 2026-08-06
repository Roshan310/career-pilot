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


class MatchListItem(BaseModel):
    """Flattened match + linked resume/job info for the dashboard and analysis list."""

    id: uuid.UUID
    status: str
    overall_score: float | None
    resume_id: uuid.UUID
    resume_file_name: str | None
    job_id: uuid.UUID
    job_title: str | None
    job_company: str | None
    created_at: datetime
