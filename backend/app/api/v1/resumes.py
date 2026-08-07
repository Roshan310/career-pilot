import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_capped(request: Request, file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload, refusing to buffer more than `max_bytes`.

    `await file.read()` pulls the entire body into memory *before* any size check
    can run, so a multi-gigabyte POST exhausted the container's memory long
    before the limit was consulted. Content-Length rejects the obvious case for
    free; the chunked loop covers a chunked or lying request.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise UnprocessableError(f"File exceeds the {settings.max_resume_file_size_mb}MB limit")

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > max_bytes:
            raise UnprocessableError(
                f"File exceeds the {settings.max_resume_file_size_mb}MB limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=ResumeResponse, status_code=201)
@limiter.limit("10/minute")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    max_bytes = settings.max_resume_file_size_mb * 1024 * 1024
    content = await _read_capped(request, file, max_bytes)
    filename = storage_service.safe_filename(file.filename)

    # Everything below is blocking: pdfplumber is CPU-bound, boto3 is sync, and
    # both LLM calls are sync HTTP. Run inline on the event loop they froze every
    # other request in the worker for the whole upload.
    raw_text = await asyncio.to_thread(extract_text, filename, content)

    file_key = await asyncio.to_thread(
        storage_service.upload_file,
        current_user.id,
        filename,
        content,
        file.content_type or "application/octet-stream",
    )

    try:
        # Concurrently, not one after the other: both take only `raw_text`, so
        # running them in sequence spent the sum of two independent round trips
        # while the user watched a spinner.
        parsed_data, embedding = await asyncio.gather(
            asyncio.to_thread(parse_resume, raw_text),
            asyncio.to_thread(embed_text, raw_text),
        )

        resume = Resume(
            user_id=current_user.id,
            file_url=file_key,
            file_name=filename,
            raw_text=raw_text,
            parsed_data=parsed_data.model_dump(),
            embedding=embedding,
        )
        db.add(resume)
        await db.commit()
    except Exception:
        # The object is already in S3 but no row will reference it. Without this
        # every failed parse left an orphan behind, and there is no GC job.
        try:
            await asyncio.to_thread(storage_service.delete_file, file_key)
        except Exception:
            logger.warning("Could not clean up orphaned upload %s", file_key, exc_info=True)
        raise

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


# The original upload has no stored content type, so it is inferred from the
# extension `safe_filename` preserved. Anything unrecognised downloads as a
# generic binary rather than being mislabelled.
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
}


@router.get("/{resume_id}/file")
async def download_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The original uploaded file.

    Streamed through the API rather than handed out as a presigned URL, for the
    same reason the interview audio endpoint gives: the JWT stays the only way
    in, and a resume is squarely the user's private data.

    The object was written on upload and, until now, only ever read again in
    order to delete it — the file the user handed us was unreachable to them.
    """
    resume = await _get_owned_resume(db, resume_id, current_user)
    if not resume.file_url:
        raise NotFoundError("No original file was stored for this resume")

    content = await asyncio.to_thread(storage_service.get_bytes, resume.file_url)
    if content is None:
        # Row survived, object didn't. Possible if a delete half-failed.
        logger.warning("Resume %s references missing object %s", resume.id, resume.file_url)
        raise NotFoundError("The stored file for this resume is no longer available")

    filename = storage_service.safe_filename(resume.file_name)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    return Response(
        content=content,
        media_type=_CONTENT_TYPES.get(extension, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = await _get_owned_resume(db, resume_id, current_user)
    file_key = resume.file_url

    # Row first. Deleting the object first meant a failed S3 call left the row
    # behind pointing at a file that no longer exists; this way the worst case is
    # an unreferenced object, which is invisible to the user and reclaimable.
    await db.delete(resume)
    await db.commit()

    if file_key:
        try:
            await asyncio.to_thread(storage_service.delete_file, file_key)
        except Exception:
            logger.warning("Resume row deleted but object %s remains", file_key, exc_info=True)
