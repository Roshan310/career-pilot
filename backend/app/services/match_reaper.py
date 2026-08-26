"""Fails matches that will never finish.

A match row is committed as `pending` before the RQ job is enqueued, and set to
`processing` by the worker before the scoring runs. Either step can be the last
thing that ever happens to it: Redis can be down when the enqueue fires, or the
worker can be killed mid-job. Nothing else in the system notices — there is no
job-level timeout and RQ does not write back to our tables — so the row stayed in
a non-terminal state forever while the client polled it indefinitely.

The sweep is deliberately dumb: anything non-terminal that hasn't been touched in
a while is declared failed. Scoring takes seconds, so the threshold has an
enormous margin and a false positive is not realistically reachable.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match

logger = logging.getLogger(__name__)

NON_TERMINAL_STATUSES = ("pending", "processing")

STALE_MESSAGE = (
    "This analysis didn't finish — the background worker may have been "
    "unavailable. Please try running it again."
)


async def sweep_stale_matches(db: AsyncSession, stale_after: timedelta) -> int:
    """Mark every match stuck past `stale_after` as failed. Returns how many.

    Keyed on `updated_at` rather than `created_at` so a job that is genuinely
    making progress (pending -> processing) gets the full window again instead of
    being reaped mid-run.
    """
    cutoff = datetime.now(UTC) - stale_after

    stale = (
        await db.execute(
            select(Match.id).where(
                Match.status.in_(NON_TERMINAL_STATUSES),
                or_(Match.updated_at < cutoff, Match.updated_at.is_(None)),
            )
        )
    ).scalars().all()

    if not stale:
        return 0

    await db.execute(
        update(Match)
        .where(Match.id.in_(stale))
        .values(status="failed", error_message=STALE_MESSAGE)
    )
    await db.commit()

    logger.warning("Reaped %d stale match(es): %s", len(stale), [str(i) for i in stale])
    return len(stale)
