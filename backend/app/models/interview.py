import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Deviation from SPECS.md §4: these three FKs get ON DELETE SET NULL (§4 leaves
    # them NO ACTION), so deleting a resume/job/match doesn't block once an interview
    # has referenced it — interview history survives.
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String, default="jd_specific", nullable=False)
    status: Mapped[str] = mapped_column(String, default="in_progress", nullable=False)
    question_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    __table_args__ = (
        # `get_turn` looks up exactly this pair on every answer submission.
        Index("idx_interview_turns_session_turn", "session_id", "turn_number"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str | None] = mapped_column(String, nullable=True)
    targets_gap: Mapped[str | None] = mapped_column(String, nullable=True)
    answer_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    speech_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SessionReport(Base):
    __tablename__ = "session_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # A session has exactly one report. Enforced in the database because
    # `complete_session`'s status check is not atomic: two concurrent completes
    # both passed it and both inserted, after which the report endpoint's
    # `scalar_one_or_none()` raised MultipleResultsFound *permanently* for that
    # user. The constraint also supplies the index for the outer join that every
    # GET /api/interviews performs.
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strengths: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    improvement_areas: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gap_coverage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Session-level rollup of interview_turns.speech_metrics (SPECS.md §7.4).
    speech_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
