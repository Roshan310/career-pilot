import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (Index("idx_matches_resume_job", "resume_id", "job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False
    )
    # Deviation from SPECS.md §4: status/error_message added so `matches.id` can
    # double as the async job_id §5 describes polling on (pending|processing|done|failed).
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    skill_overlap_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    keyword_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_skills: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggestions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ats_issues: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
