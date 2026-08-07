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
from app.schemas.job import JobCreateRequest, JobListItem, JobResponse
from app.services.embeddings import embed_text
from app.services.llm.job_parsing import parse_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
        .order_by(JobDescription.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobDescription).where(JobDescription.id == job_id, JobDescription.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job description not found")
    return job
