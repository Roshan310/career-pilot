import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.resume import EMBEDDING_DIM


# The application pipeline. Ordered — the UI groups columns in this sequence,
# and `saved` is the state every job starts in.
JOB_STATUSES = ("saved", "applied", "screening", "interviewing", "offer", "rejected")
JOB_PRIORITIES = ("low", "normal", "high")


class JobDescription(Base):
    """A saved job posting, and the application against it.

    Started life as a write-once record — parse a JD, match a resume, done. The
    tracking columns below are what make it something a user comes back to: a
    job seeker keeps this state in a spreadsheet either way, so it may as well
    live next to the matching and interview practice it feeds.
    """

    __tablename__ = "job_descriptions"
    __table_args__ = (
        # The board groups by status per user; this is the exact lookup.
        Index("idx_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    # ---- application tracking ----
    status: Mapped[str] = mapped_column(String, default="saved", server_default="saved", nullable=False)
    priority: Mapped[str] = mapped_column(
        String, default="normal", server_default="normal", nullable=False
    )
    # Calendar dates, not timestamps: "applied on the 3rd" and "closes Friday"
    # have no meaningful time-of-day, and storing them as instants would shift
    # the displayed day across timezones.
    applied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
