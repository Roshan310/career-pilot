import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


class ParsedJobRequirements(BaseModel):
    """SPECS.md §6.1 job `parsed_requirements` schema."""

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    seniority_level: str | None = None
    # Float, not int. Sub-year requirements are real ("3+ months", internships)
    # and the model returns them as such — 0.25 against an int field was a hard
    # 502 that no retry could fix. Every consumer already treats this as a real
    # number: matching_service does `sqrt(candidate / required)` and the frontend
    # types it `number`, so int was the odd one out.
    years_experience_required: float | None = Field(default=None, ge=0)
    key_responsibilities: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    # Upper bound matters as much as the lower one: this text goes straight into
    # an LLM prompt and an embedding call, and had no maximum while resume
    # uploads were capped at 10MB.
    raw_text: str = Field(min_length=1, max_length=settings.max_job_description_chars)


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
