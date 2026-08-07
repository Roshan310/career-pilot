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


class ProjectItem(BaseModel):
    """A personal, academic or open-source project.

    First-class rather than lumped into `additional_sections` because it is
    near-universal and because it carries real scoring signal: for an
    early-career candidate the projects section *is* the evidence. Before this
    existed the schema had nowhere to put it, so the model silently dropped
    entire projects sections.
    """

    name: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    url: str | None = None


class AdditionalSection(BaseModel):
    """Any heading the fixed fields don't cover — publications, awards,
    languages, volunteering, leadership.

    The catch-all exists so nothing is silently discarded again. Deliberately
    unstructured: the whole point is that we don't know in advance what a resume
    will contain, and guessing a schema for every possible heading is how the
    projects hole appeared in the first place.
    """

    heading: str
    items: list[str] = Field(default_factory=list)


class ParsedResumeData(BaseModel):
    """SPECS.md §6.1 resume `parsed_data` schema."""

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    additional_sections: list[AdditionalSection] = Field(default_factory=list)


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
