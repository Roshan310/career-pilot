import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, UnprocessableError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeListItem, ResumeResponse
from app.services import storage_service
from app.services.embeddings import embed_text
from app.services.llm.resume_parsing import parse_resume
from app.services.resume_parser import extract_text

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()


@router.post("", response_model=ResumeResponse, status_code=201)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    max_bytes = settings.max_resume_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise UnprocessableError(f"File exceeds the {settings.max_resume_file_size_mb}MB limit")

    raw_text = extract_text(file.filename, content)

    file_key = storage_service.upload_file(
        current_user.id, file.filename, content, file.content_type or "application/octet-stream"
    )

    parsed_data = parse_resume(raw_text)
    embedding = embed_text(raw_text)

    resume = Resume(
        user_id=current_user.id,
        file_url=file_key,
        file_name=file.filename,
        raw_text=raw_text,
        parsed_data=parsed_data.model_dump(),
        embedding=embedding,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


async def _get_owned_resume(db: AsyncSession, resume_id: uuid.UUID, user: User) -> Resume:
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise NotFoundError("Resume not found")
    return resume


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned_resume(db, resume_id, current_user)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await _get_owned_resume(db, resume_id, current_user)
    if resume.file_url:
        storage_service.delete_file(resume.file_url)
    await db.delete(resume)
    await db.commit()
