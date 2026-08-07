import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str | None = None
    institution: str | None = None
    year: str | None = None


class ParsedResumeData(BaseModel):
    """SPECS.md §6.1 resume `parsed_data` schema."""

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ResumeResponse(BaseModel):
    id: uuid.UUID
    file_name: str | None
    has_file: bool = False
    raw_text: str
    parsed_data: dict
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeListItem(BaseModel):
    id: uuid.UUID
    file_name: str | None
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
