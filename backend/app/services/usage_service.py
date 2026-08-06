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


async def check_limit(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Enforce the free-tier monthly limit BEFORE any LLM call is triggered
    (SPECS.md §9). No paid tiers exist yet (billing is deferred), so every user is
    checked against the free-tier limit.

    Deliberately does NOT increment. The two halves are separate because the work
    being metered can fail *after* the check — question generation is a 5-15s LLM
    call, and a Gemini 429 there used to burn a month's quota on an interview that
    never existed. Call `increment()` only once the thing the user is paying for
    is actually in the database."""
    _reset_if_needed(user)

    limit = _LIMITS[kind]
    if getattr(user, _COUNT_ATTR[kind]) >= limit:
        db.add(user)
        await db.commit()  # persist a reset that may have just happened, even on the rejected path
        raise UsageLimitExceededError(
            f"Monthly {kind} limit reached ({limit}). Resets at {user.usage_reset_at.isoformat()}."
        )


async def increment(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Charge the user for one unit of `kind`. Must run after `check_limit`."""
    count_attr = _COUNT_ATTR[kind]
    setattr(user, count_attr, getattr(user, count_attr) + 1)
    db.add(user)
    await db.commit()


async def check_and_increment(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Both halves at once — correct only where nothing between the check and the
    commit of the metered record can fail. Matching qualifies: the Match row is
    written immediately and the LLM work happens later in the RQ worker. Interview
    creation does not; see `check_limit`."""
    await check_limit(db, user, kind)
    await increment(db, user, kind)


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
