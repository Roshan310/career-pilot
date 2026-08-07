from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select, update
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


def _apply_reset(user: User) -> None:
    """Zero the counters if the window has rolled over. Caller must hold the row
    lock — two concurrent requests both resetting was itself a way to lose a
    charge."""
    now = datetime.now(UTC)
    if user.usage_reset_at is None or now >= user.usage_reset_at:
        user.monthly_match_count = 0
        user.monthly_interview_count = 0
        user.usage_reset_at = now + timedelta(days=30)


async def _lock_and_reset(db: AsyncSession, user: User) -> User:
    """Re-read the user's row under `FOR UPDATE` and apply any pending reset.

    Everything that reads a counter and then writes it needs this. Without the
    lock, two requests sitting at limit-1 both read "under the limit" and both
    proceed, so the limit is not actually a limit. `populate_existing` forces the
    already-identity-mapped instance to take the freshly locked values rather
    than serving whatever it was loaded with earlier in the request.
    """
    locked = (
        await db.execute(
            select(User)
            .where(User.id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    _apply_reset(locked)
    return locked


def _reject(kind: UsageKind, user: User) -> None:
    limit = _LIMITS[kind]
    raise UsageLimitExceededError(
        f"Monthly {kind} limit reached ({limit}). Resets at {user.usage_reset_at.isoformat()}."
    )


async def check_limit(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Enforce the free-tier monthly limit BEFORE any LLM call is triggered
    (SPECS.md §9). No paid tiers exist yet (billing is deferred), so every user is
    checked against the free-tier limit.

    Deliberately does NOT increment. The two halves are separate because the work
    being metered can fail *after* the check — question generation is a 5-15s LLM
    call, and a Gemini 429 there used to burn a month's quota on an interview that
    never existed. Call `increment()` only once the thing the user is paying for
    is actually in the database.

    The gap between the two halves is a deliberate over-count risk, not an
    over-count guarantee: worst case a user who fires two interview creations in
    the same instant gets one extra. Closing it would mean either charging for
    failed generations or deleting a session the user is already looking at.
    """
    locked = await _lock_and_reset(db, user)
    over = getattr(locked, _COUNT_ATTR[kind]) >= _LIMITS[kind]
    # Commits either way — the lock must be released, and a reset that just
    # happened has to persist even on the rejected path.
    await db.commit()
    if over:
        _reject(kind, locked)


async def increment(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Charge the user for one unit of `kind`. Must run after `check_limit`.

    A single atomic `count = count + 1` in the database, not a read-modify-write
    in Python: two concurrent charges both read N and both wrote N+1, so one of
    them silently vanished and the user got free usage.

    Never rejects. By the time this runs the thing being charged for already
    exists — failing here would leave an orphaned session and take away work the
    user can see.
    """
    count_attr = _COUNT_ATTR[kind]
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values({count_attr: getattr(User, count_attr) + 1})
    )
    await db.commit()
    await db.refresh(user)


async def check_and_increment(db: AsyncSession, user: User, kind: UsageKind) -> None:
    """Both halves at once — correct only where nothing between the check and the
    commit of the metered record can fail. Matching qualifies: the Match row is
    written immediately and the LLM work happens later in the RQ worker. Interview
    creation does not; see `check_limit`.

    Because there is no gap here, this one is genuinely atomic: the check and the
    charge happen under the same row lock, in the same transaction.
    """
    locked = await _lock_and_reset(db, user)
    count_attr = _COUNT_ATTR[kind]
    if getattr(locked, count_attr) >= _LIMITS[kind]:
        await db.commit()
        _reject(kind, locked)

    setattr(locked, count_attr, getattr(locked, count_attr) + 1)
    await db.commit()


async def usage_snapshot(db: AsyncSession, user: User) -> dict:
    locked = await _lock_and_reset(db, user)
    await db.commit()
    return {
        "monthly_match_count": locked.monthly_match_count,
        "monthly_match_limit": _LIMITS["match"],
        "monthly_interview_count": locked.monthly_interview_count,
        "monthly_interview_limit": _LIMITS["interview"],
        "usage_reset_at": locked.usage_reset_at,
    }
