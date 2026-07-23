import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ParsedJobRequirements(BaseModel):
    """SPECS.md §6.1 job `parsed_requirements` schema."""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    years_experience_required: int | None = None
    key_responsibilities: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    title: str | None = None
    company: str | None = None
    raw_text: str = Field(min_length=1)


class JobResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    raw_text: str
    parsed_requirements: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class JobListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    company: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
