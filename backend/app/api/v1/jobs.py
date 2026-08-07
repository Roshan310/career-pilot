import asyncio
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.job_description import JobDescription
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobListItem, JobResponse, JobUpdateRequest
from app.services.embeddings import embed_text
from app.services.llm.job_parsing import parse_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _get_owned_job(db: AsyncSession, job_id: uuid.UUID, user: User) -> JobDescription:
    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == job_id, JobDescription.user_id == user.id
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job description not found")
    return job


@router.post("", response_model=JobResponse, status_code=201)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    body: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Both are blocking, multi-second HTTP calls — off the event loop so one job
    # submission doesn't stall every other request in the worker.
    parsed_requirements = await asyncio.to_thread(parse_job, body.raw_text)
    embedding = await asyncio.to_thread(embed_text, body.raw_text)

    job = JobDescription(
        user_id=current_user.id,
        title=body.title,
        company=body.company,
        raw_text=body.raw_text,
        parsed_requirements=parsed_requirements.model_dump(),
        embedding=embedding,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobListItem])
async def list_jobs(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        # Most recently touched first — a status change should float a job back
        # to the top, which created_at cannot express.
        .order_by(JobDescription.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_job(db, job_id, current_user)


@router.patch("/{job_id}", response_model=JobResponse)
@limiter.limit("60/minute")
async def update_job(
    request: Request,
    job_id: uuid.UUID,
    body: JobUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit the posting's label or its application state.

    Deliberately does NOT re-parse or re-embed: `raw_text` is not editable here.
    Changing it would invalidate every match already computed against this job,
    and re-running the LLM on a status change would be absurd. Replacing the
    posting text means creating a new job.

    `exclude_unset` matters — None is a real value (clearing a deadline), so
    "leave this alone" has to be expressed by omitting the key.
    """
    job = await _get_owned_job(db, job_id, current_user)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a job and everything computed from it.

    `matches.job_id` is ON DELETE CASCADE, so this takes the match history with
    it. `interview_sessions.job_id` is ON DELETE SET NULL, so past interviews
    survive but lose the link. The client warns about both before calling this.
    """
    job = await _get_owned_job(db, job_id, current_user)
    await db.delete(job)
    await db.commit()
