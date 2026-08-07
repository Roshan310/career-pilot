import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError, UnprocessableError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.interview import InterviewSession, SessionReport
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewListItem,
    InterviewSessionResponse,
    SessionReportResponse,
    TranscriptionResponse,
    TurnSubmitRequest,
    TurnSubmitResponse,
)
from app.services import interview_service, transcription, tts
from app.services.usage_service import check_limit, increment

_AUDIO_CHUNK_BYTES = 1024 * 1024


async def _read_capped_audio(request: Request, audio: UploadFile) -> bytes:
    """Read an answer recording, refusing to buffer past the transcription limit.

    `await audio.read()` pulled the whole body into memory first and only then
    handed it to `transcribe_answer`, which is where the 25MB check lives — so
    the check could not protect the thing it was there to protect.
    """
    limit = transcription.MAX_AUDIO_BYTES
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise UnprocessableError("Audio file is too large.")

    chunks: list[bytes] = []
    total = 0
    while chunk := await audio.read(_AUDIO_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise UnprocessableError("Audio file is too large.")
        chunks.append(chunk)
    return b"".join(chunks)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])


async def _get_owned_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> InterviewSession:
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("Interview session not found")
    return session


@router.post("", response_model=InterviewSessionResponse, status_code=201)
@limiter.limit("10/minute")
async def create_interview(
    request: Request,
    body: InterviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resume = (
        await db.execute(select(Resume).where(Resume.id == body.resume_id, Resume.user_id == current_user.id))
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

    match = None
    if body.match_id is not None:
        match = (
            await db.execute(
                select(Match).join(Resume, Match.resume_id == Resume.id).where(
                    Match.id == body.match_id, Resume.user_id == current_user.id
                )
            )
        ).scalar_one_or_none()
        if match is None:
            raise NotFoundError("Match not found")

    # Checked BEFORE the question-generation LLM call (SPECS.md §9) so an
    # over-limit request never spends one, but charged only AFTER the session
    # exists — start_session can raise LLMServiceError on a Gemini 429, and a
    # failed start must not cost the user an interview.
    await check_limit(db, current_user, "interview")

    session = await interview_service.start_session(db, current_user, resume, job, match, body.mode)
    await increment(db, current_user, "interview")

    return await interview_service.build_session_response(db, session)


@router.get("", response_model=list[InterviewListItem])
async def list_interviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            InterviewSession,
            JobDescription.title,
            JobDescription.company,
            SessionReport.overall_score,
        )
        .outerjoin(JobDescription, InterviewSession.job_id == JobDescription.id)
        .outerjoin(SessionReport, SessionReport.session_id == InterviewSession.id)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.started_at.desc())
    )

    items: list[InterviewListItem] = []
    for session, title, company, overall_score in result.all():
        duration_minutes = None
        if session.ended_at is not None:
            duration_minutes = round((session.ended_at - session.started_at).total_seconds() / 60, 1)
        items.append(
            InterviewListItem(
                id=session.id,
                mode=session.mode,
                status=session.status,
                job_title=title,
                job_company=company,
                overall_score=overall_score,
                started_at=session.started_at,
                ended_at=session.ended_at,
                duration_minutes=duration_minutes,
            )
        )
    return items


@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    return await interview_service.build_session_response(db, session)


@router.post("/{session_id}/turns", response_model=TurnSubmitResponse)
@limiter.limit("30/minute")
async def submit_turn(
    request: Request,
    session_id: uuid.UUID,
    body: TurnSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    return await interview_service.submit_answer(db, session, body)


@router.get("/{session_id}/turns/{turn_number}/audio")
@limiter.limit("30/minute")
async def get_turn_audio(
    request: Request,
    session_id: uuid.UUID,
    turn_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The question, spoken. Streams bytes through the API rather than handing out
    a presigned URL so the JWT stays the only way in — the audio is as much the
    user's private interview data as the transcript is.

    A 503 here is expected and survivable: the client falls back to the browser's
    own voice. That's why the TTS layer raises its own exception type instead of
    an AppError — a missing voice must never read as a broken interview.
    """
    session = await _get_owned_session(db, session_id, current_user)

    turn = await interview_service.get_turn(db, session.id, turn_number)
    if turn is None:
        raise NotFoundError("Turn not found")

    try:
        # Sync boto3 + a ~1s HTTP round trip. Off the event loop, or one slow
        # synthesis stalls every other request the API is serving.
        audio = await asyncio.to_thread(tts.question_audio, session.id, turn_number, turn.question_text)
    except tts.TTSUnavailableError as exc:
        logger.info("question audio unavailable for %s turn %s: %s", session_id, turn_number, exc)
        raise ServiceUnavailableError("Question audio is unavailable.") from exc

    return Response(
        content=audio,
        media_type=tts.CONTENT_TYPE,
        # Same bytes for the life of the turn — let the browser skip the refetch
        # on a replay, and private because this is one user's interview.
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/{session_id}/transcribe", response_model=TranscriptionResponse)
@limiter.limit("30/minute")
async def transcribe_answer(
    request: Request,
    session_id: uuid.UUID,
    audio: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Turn a recorded answer into text. Deliberately separate from `submit_turn`:
    if these were one call, a transcription failure would destroy an answer the
    candidate already gave, and the client's retry path depends on holding a
    complete envelope before anything can go wrong with sending it.
    """
    await _get_owned_session(db, session_id, current_user)  # ownership check

    content = await _read_capped_audio(request, audio)
    transcript = await asyncio.to_thread(
        transcription.transcribe_answer, content, audio.content_type
    )
    return TranscriptionResponse(transcript=transcript)


@router.post("/{session_id}/complete", response_model=SessionReportResponse)
# Was the only unlimited write endpoint, and it runs a full report aggregation
# on every call — which is also what made the duplicate-report race easy to hit.
# Generous, because completing is idempotent and a client retry is legitimate.
@limiter.limit("20/minute")
async def complete_interview(
    request: Request,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    return await interview_service.complete_session(db, session)


@router.post("/{session_id}/abandon", response_model=InterviewSessionResponse)
@limiter.limit("20/minute")
async def abandon_interview(
    request: Request,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    session = await interview_service.abandon_session(db, session)
    return await interview_service.build_session_response(db, session)


@router.get("/{session_id}/report", response_model=SessionReportResponse)
async def get_interview_report(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_session(db, session_id, current_user)  # ownership check
    result = await db.execute(select(SessionReport).where(SessionReport.session_id == session_id))
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundError("Report not found — interview may not be completed yet")
    return report
