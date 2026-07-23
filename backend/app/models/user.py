import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    auth_provider_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_tier: Mapped[str] = mapped_column(String, default="free", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    monthly_match_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_interview_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
