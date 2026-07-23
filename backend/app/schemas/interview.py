import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class QuestionPlanItem(BaseModel):
    question_text: str
    question_type: str = "main"
    targets_gap: str | None = None
    based_on: str | None = None


class QuestionPlan(BaseModel):
    questions: list[QuestionPlanItem]

    @field_validator("questions")
    @classmethod
    def _reasonable_count(cls, v: list[QuestionPlanItem]) -> list[QuestionPlanItem]:
        if not v:
            raise ValueError("question plan must contain at least one question")
        return v


class InterviewCreateRequest(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID
    match_id: uuid.UUID | None = None
    mode: str = "jd_specific"


class CurrentQuestion(BaseModel):
    turn_number: int
    question_text: str
    question_type: str | None
    targets_gap: str | None


class InterviewSessionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    question_plan: list | None
    started_at: datetime
    ended_at: datetime | None
    current_question: CurrentQuestion | None = None

    model_config = {"from_attributes": True}


class TurnSubmitRequest(BaseModel):
    question_number: int = Field(ge=1)
    answer_transcript: str
    duration: float = Field(ge=0)


class EvaluationResult(BaseModel):
    structure: int | None = None
    specificity: int | None = None
    relevance: int | None = None


class TurnSubmitResponse(BaseModel):
    session_status: str  # in_progress | wrapping_up
    evaluation: EvaluationResult | None = None
    next_question: CurrentQuestion | None = None


class SessionReportResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    overall_score: float | None
    strengths: list | None
    improvement_areas: list | None
    gap_coverage: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
