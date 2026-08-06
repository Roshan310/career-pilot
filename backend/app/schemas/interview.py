import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

# `question_type` on a turn is a control flag the state machine reads — it decides
# plan advancement and the follow-up cap. Only these two values mean anything.
CONTROL_QUESTION_TYPES = ("main", "follow_up")


class QuestionPlanItem(BaseModel):
    question_text: str
    question_type: str = "main"
    # The LLM's own descriptive label ("Technical/Gap", "Behavioral"), kept for
    # display. Separate from question_type on purpose — see the validator below.
    category: str | None = None
    targets_gap: str | None = None
    based_on: str | None = None

    @field_validator("question_type", "category", "targets_gap", "based_on", mode="before")
    @classmethod
    def _first_of_list(cls, v: object, info: ValidationInfo) -> object:
        """§7.1's prompt names these fields but constrains neither their values
        nor their types, so the model answers in whatever shape fits the
        question. A question probing several related gaps comes back as
        `targets_gap: ["Distributed Systems", "Scalability", ...]`, which failed
        field validation and killed the entire plan — no interview could start.

        Keep the FIRST entry, not a joined string. `targets_gap` is a join key:
        `aggregate_report()` intersects it with `missing_skills[].skill`, so
        "Distributed Systems, Scalability" would match no skill at all and every
        gap in the list would read as still-open forever. The first entry at
        least matches one. An empty list means "no gap", i.e. None.

        This runs mode="before" on purpose — field validation rejects a list
        before any mode="after" validator (like the one below) ever runs.
        """
        if not isinstance(v, list):
            return v
        first = next((item for item in v if isinstance(item, str) and item.strip()), None)
        # question_type is the one non-nullable field here; an empty list has to
        # land on the default rather than None, or we'd swap one 500 for another.
        if first is None and info.field_name == "question_type":
            return "main"
        return first

    @model_validator(mode="after")
    def _keep_question_type_a_control_flag(self) -> "QuestionPlanItem":
        """§7.1's prompt asks the LLM for a `question_type` but never constrains it,
        so Gemini returns descriptive categories ("Technical Deep Dive"). Those used
        to land directly on the turn, where `main_question_count()` counts
        `question_type == "main"` — with no turn ever matching, the plan index stayed
        at 0 and the interview re-asked question 1 forever, capped only by the
        20-minute wall clock. Every planned question IS a main question, so the label
        moves to `category` and the control flag is forced back to "main"."""
        if self.question_type not in CONTROL_QUESTION_TYPES:
            if self.category is None:
                self.category = self.question_type
            self.question_type = "main"
        return self


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


class EvaluationResult(BaseModel):
    structure: int | None = None
    specificity: int | None = None
    relevance: int | None = None


class SessionProgress(BaseModel):
    """What the live session UI needs to render a progress bar and a countdown.
    Derived from the same state-machine functions that enforce the caps, so the
    UI and the server can't disagree about when the interview ends."""

    main_questions_answered: int
    main_questions_planned: int
    follow_ups_used: int
    max_follow_ups_per_question: int
    seconds_remaining: float
    hard_cap_minutes: int
    hard_capped: bool


class TurnDetail(BaseModel):
    turn_number: int
    question_text: str
    question_type: str | None
    targets_gap: str | None
    answer_transcript: str | None
    answer_duration_seconds: float | None
    score: EvaluationResult | None
    speech_metrics: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    question_plan: list | None
    started_at: datetime
    ended_at: datetime | None
    current_question: CurrentQuestion | None = None
    # Full turn history — needed both to restore a live session after a reconnect
    # and to render the per-answer breakdown on the report page.
    turns: list[TurnDetail] = []
    progress: SessionProgress | None = None

    model_config = {"from_attributes": True}


class TranscriptSegment(BaseModel):
    """One contiguous chunk of speech with its timing, in milliseconds relative to
    the start of the answer.

    This is the provider-agnostic unit that keeps the voice layer swappable
    (SPECS.md §7.6, extended to the backend): the Web Speech API gives interim
    results the client can turn into rough segments, while a server-side
    streaming provider gives real word timings — same shape from either, so
    services/speech_metrics.py never learns which one is in use.
    """

    text: str
    start_ms: float = Field(ge=0)
    end_ms: float = Field(ge=0)


class TurnSubmitRequest(BaseModel):
    question_number: int = Field(ge=1)
    answer_transcript: str
    duration: float = Field(ge=0)
    # Which voice layer produced answer_transcript. "server_stt" is unused today —
    # it's the value a future WebSocket/streaming-STT transport will send.
    source: str = "browser_speech"  # browser_speech | typed | server_stt
    segments: list[TranscriptSegment] | None = None
    # §7.2: no speech captured after the retry prompt. Advances the interview
    # without an evaluation LLM call.
    skipped: bool = False


class TranscriptionResponse(BaseModel):
    """An empty transcript is a valid answer to "what did they say?" — it means
    the clip held no intelligible speech, and the client submits that turn as
    skipped rather than treating it as a failure."""

    transcript: str


class TurnSubmitResponse(BaseModel):
    session_status: str  # in_progress | wrapping_up
    evaluation: EvaluationResult | None = None
    next_question: CurrentQuestion | None = None
    speech_metrics: dict | None = None
    progress: SessionProgress | None = None


class InterviewListItem(BaseModel):
    """Flattened session + linked job/report info for the interview-history list."""

    id: uuid.UUID
    mode: str
    status: str
    job_title: str | None
    job_company: str | None
    overall_score: float | None
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: float | None


class SessionReportResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    overall_score: float | None
    strengths: list | None
    improvement_areas: list | None
    gap_coverage: dict | None
    speech_metrics: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
