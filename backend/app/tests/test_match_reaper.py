"""The sweep that fails matches which will never finish.

A match is committed as `pending` before the RQ job is enqueued and set to
`processing` by the worker before scoring runs. Either can be the last thing that
ever happens to it — Redis down at enqueue time, or a worker killed mid-job — and
nothing else in the system notices, so the row sat non-terminal forever while the
client polled it.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.services.auth_service import register_user
from app.services.match_reaper import STALE_MESSAGE, sweep_stale_matches

EMBEDDING = [0.1] * 1536
STALE_AFTER = timedelta(minutes=10)


@pytest.fixture
async def owned_match(db_session):
    user = await register_user(db_session, "reaper@example.com", "password123", None)
    resume = Resume(user_id=user.id, raw_text="x", parsed_data={"skills": []}, embedding=EMBEDDING)
    job = JobDescription(
        user_id=user.id, raw_text="x", parsed_requirements={"required_skills": []}, embedding=EMBEDDING
    )
    db_session.add_all([resume, job])
    await db_session.commit()

    async def _make(status: str, age: timedelta) -> Match:
        match = Match(resume_id=resume.id, job_id=job.id, status=status)
        db_session.add(match)
        await db_session.commit()
        # onupdate would overwrite a value set on insert, so age the row after.
        match.updated_at = datetime.now(UTC) - age
        await db_session.commit()
        await db_session.refresh(match)
        return match

    return _make


@pytest.mark.parametrize("status", ["pending", "processing"])
async def test_a_stuck_match_is_failed(db_session, owned_match, status):
    match = await owned_match(status, timedelta(hours=1))

    assert await sweep_stale_matches(db_session, STALE_AFTER) == 1

    await db_session.refresh(match)
    assert match.status == "failed"
    # The message has to tell the user what to do, not just that it broke.
    assert match.error_message == STALE_MESSAGE


@pytest.mark.parametrize("status", ["done", "failed"])
async def test_terminal_matches_are_left_alone(db_session, owned_match, status):
    match = await owned_match(status, timedelta(hours=1))

    assert await sweep_stale_matches(db_session, STALE_AFTER) == 0

    await db_session.refresh(match)
    assert match.status == status


async def test_a_match_still_inside_the_window_is_left_alone(db_session, owned_match):
    """Scoring takes seconds; a job that started a moment ago is healthy."""
    match = await owned_match("processing", timedelta(seconds=5))

    assert await sweep_stale_matches(db_session, STALE_AFTER) == 0

    await db_session.refresh(match)
    assert match.status == "processing"


async def test_progress_resets_the_clock(db_session, owned_match):
    """Keyed on updated_at, not created_at: a long-queued job that has just moved
    to `processing` gets the full window again rather than being reaped mid-run."""
    match = await owned_match("pending", timedelta(hours=1))

    match.status = "processing"  # onupdate refreshes updated_at
    await db_session.commit()

    assert await sweep_stale_matches(db_session, STALE_AFTER) == 0
    await db_session.refresh(match)
    assert match.status == "processing"


async def test_the_sweep_is_idempotent(db_session, owned_match):
    await owned_match("pending", timedelta(hours=1))

    assert await sweep_stale_matches(db_session, STALE_AFTER) == 1
    # Every replica runs the loop; a second pass must be a no-op, not a rewrite.
    assert await sweep_stale_matches(db_session, STALE_AFTER) == 0


async def test_an_empty_sweep_touches_nothing(db_session):
    assert await sweep_stale_matches(db_session, STALE_AFTER) == 0
