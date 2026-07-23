import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.schemas.match import MatchCreateRequest, MatchResponse, MatchStatusResponse, SuggestionsResponse
from app.services.usage_service import check_and_increment
from app.workers.queue import enqueue_matching_job

router = APIRouter(prefix="/matches", tags=["matches"])


async def _get_owned_match(db: AsyncSession, match_id: uuid.UUID, user: User) -> Match:
    result = await db.execute(
        select(Match).join(Resume, Match.resume_id == Resume.id).where(
            Match.id == match_id, Resume.user_id == user.id
        )
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundError("Match not found")
    return match


@router.post("", response_model=MatchStatusResponse, status_code=202)
@limiter.limit("10/minute")
async def create_match(
    request: Request,
    body: MatchCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = (
        await db.execute(
            select(Resume).where(Resume.id == body.resume_id, Resume.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if resume is None:
        raise NotFoundError("Resume not found")

    job = (
        await db.execute(
            select(JobDescription).where(
                JobDescription.id == body.job_id, JobDescription.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job description not found")

    # Usage limit enforced BEFORE any LLM call is triggered (SPECS.md §9) —
    # the matching job itself is where the LLM calls (suggestions) happen.
    await check_and_increment(db, current_user, "match")

    match = Match(resume_id=resume.id, job_id=job.id, status="pending")
    db.add(match)
    await db.commit()
    await db.refresh(match)

    enqueue_matching_job(str(match.id))

    return MatchStatusResponse(id=match.id, status=match.status)


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_match(db, match_id, current_user)


@router.get("/{match_id}/suggestions", response_model=SuggestionsResponse)
async def get_match_suggestions(
    match_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    match = await _get_owned_match(db, match_id, current_user)
    return SuggestionsResponse(suggestions=match.suggestions or [])
