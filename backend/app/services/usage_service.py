from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import UsageLimitExceededError
from app.models.user import User

settings = get_settings()

UsageKind = Literal["match", "interview"]

_LIMITS = {
    "match": settings.free_tier_monthly_match_limit,
    "interview": settings.free_tier_monthly_interview_limit,
}
_COUNT_ATTR = {"match": "monthly_match_count", "interview": "monthly_interview_count"}


def _reset_if_needed(user: User) -> None:
    now = datetime.now(UTC)
    if user.usage_reset_at is None or now >= user.usage_reset_at:
        user.monthly_match_count = 0
        user.monthly_interview_count = 0
        user.usage_reset_at = now + timedelta(days=30)


async def check_and_increment(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Enforce the free-tier monthly limit BEFORE any LLM call is triggered
    (SPECS.md §9), then increment. No paid tiers exist yet (billing is deferred),
    so every user is checked against the free-tier limit."""
    _reset_if_needed(user)

    limit = _LIMITS[kind]
    count_attr = _COUNT_ATTR[kind]
    current_count = getattr(user, count_attr)

    if current_count >= limit:
        db.add(user)
        await db.commit()  # persist a reset that may have just happened, even on the rejected path
        raise UsageLimitExceededError(
            f"Monthly {kind} limit reached ({limit}). Resets at {user.usage_reset_at.isoformat()}."
        )

    setattr(user, count_attr, current_count + 1)
    db.add(user)
    await db.commit()


async def usage_snapshot(db: AsyncSession, user: User) -> dict:
    _reset_if_needed(user)
    db.add(user)
    await db.commit()
    return {
        "monthly_match_count": user.monthly_match_count,
        "monthly_match_limit": _LIMITS["match"],
        "monthly_interview_count": user.monthly_interview_count,
        "monthly_interview_limit": _LIMITS["interview"],
        "usage_reset_at": user.usage_reset_at,
    }
