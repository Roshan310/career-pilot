import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.interview import InterviewSession, InterviewTurn, SessionReport
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import (
    CurrentQuestion,
    InterviewCreateRequest,
    InterviewSessionResponse,
    SessionReportResponse,
    TurnSubmitRequest,
    TurnSubmitResponse,
)
from app.services import interview_state_machine as sm
from app.services.llm.answer_evaluation import evaluate_answer
from app.services.llm.question_generation import generate_question_plan
from app.services.usage_service import check_and_increment

router = APIRouter(prefix="/interviews", tags=["interviews"])


async def _get_owned_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> InterviewSession:
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("Interview session not found")
    return session


async def _get_turns(db: AsyncSession, session_id: uuid.UUID) -> list[InterviewTurn]:
    result = await db.execute(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_number)
    )
    return list(result.scalars().all())


def _pending_question(turns: list[InterviewTurn]) -> CurrentQuestion | None:
    for turn in turns:
        if turn.answer_transcript is None:
            return CurrentQuestion(
                turn_number=turn.turn_number,
                question_text=turn.question_text,
                question_type=turn.question_type,
                targets_gap=turn.targets_gap,
            )
    return None


async def _session_response(db: AsyncSession, session: InterviewSession) -> InterviewSessionResponse:
    turns = await _get_turns(db, session.id)
    response = InterviewSessionResponse.model_validate(session)
    response.current_question = _pending_question(turns)
    return response


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

    missing_skills: list = []
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
        missing_skills = match.missing_skills or []

    # Usage limit enforced BEFORE the question-generation LLM call (SPECS.md §9).
    await check_and_increment(db, current_user, "interview")

    question_plan = generate_question_plan(resume.parsed_data, job.parsed_requirements, missing_skills)

    session = InterviewSession(
        user_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        match_id=body.match_id,
        mode=body.mode,
        status="in_progress",
        question_plan=[q.model_dump() for q in question_plan.questions],
    )
    db.add(session)
    await db.flush()

    first_question = question_plan.questions[0]
    db.add(
        InterviewTurn(
            session_id=session.id,
            turn_number=1,
            question_text=first_question.question_text,
            question_type=first_question.question_type,
            targets_gap=first_question.targets_gap,
        )
    )
    await db.commit()
    await db.refresh(session)

    return await _session_response(db, session)


@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    return await _session_response(db, session)


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
    if session.status != "in_progress":
        raise ConflictError(f"Interview session is '{session.status}', not accepting answers")

    turns = await _get_turns(db, session_id)
    pending = _pending_question(turns)
    if pending is None or pending.turn_number != body.question_number:
        raise ConflictError(
            f"Expected an answer for question {pending.turn_number if pending else 'none pending'}, "
            f"got {body.question_number}"
        )

    turn = next(t for t in turns if t.turn_number == body.question_number)
    turn.answer_transcript = body.answer_transcript
    turn.answer_duration_seconds = body.duration

    based_on = turn.targets_gap or turn.question_text
    try:
        evaluation = evaluate_answer(turn.question_text, based_on, body.answer_transcript)
        turn.score = {
            "structure": evaluation.structure,
            "specificity": evaluation.specificity,
            "relevance": evaluation.relevance,
        }
        llm_next_action, llm_follow_up = evaluation.next_action, evaluation.follow_up_question
    except Exception:
        # graceful degradation (§9): scoring this turn failed, but the
        # interview keeps moving rather than the whole request failing.
        turn.score = None
        llm_next_action, llm_follow_up = "next_question", None

    await db.flush()
    turns = await _get_turns(db, session_id)  # refresh with the now-answered turn included

    next_step = sm.decide_next_step(
        session, turns, session.question_plan or [], turn, llm_next_action, llm_follow_up
    )

    if next_step["action"] == "wrap_up":
        await db.commit()
        return TurnSubmitResponse(
            session_status="wrapping_up",
            evaluation=turn.score,
            next_question=None,
        )

    next_turn = InterviewTurn(
        session_id=session.id,
        turn_number=body.question_number + 1,
        question_text=next_step["question_text"],
        question_type=next_step["question_type"],
        targets_gap=next_step.get("targets_gap"),
    )
    db.add(next_turn)
    await db.commit()

    return TurnSubmitResponse(
        session_status="in_progress",
        evaluation=turn.score,
        next_question=CurrentQuestion(
            turn_number=next_turn.turn_number,
            question_text=next_turn.question_text,
            question_type=next_turn.question_type,
            targets_gap=next_turn.targets_gap,
        ),
    )


def _aggregate_report(turns: list[InterviewTurn], missing_skills: list[dict]) -> dict:
    scored = [t for t in turns if t.answer_transcript is not None and t.score]

    def turn_avg(t: InterviewTurn) -> float:
        s = t.score
        return (s["structure"] + s["specificity"] + s["relevance"]) / 3

    weight = {"main": 1.0, "follow_up": 0.5}
    weighted_sum = sum(turn_avg(t) * weight.get(t.question_type, 1.0) for t in scored)
    weight_total = sum(weight.get(t.question_type, 1.0) for t in scored)
    overall_score = (weighted_sum / weight_total) if weight_total else None

    strengths = [
        {"turn_number": t.turn_number, "question_text": t.question_text}
        for t in scored
        if t.score["structure"] >= 4 and t.score["specificity"] >= 4 and t.score["relevance"] >= 4
    ]
    improvement_areas = [
        {"turn_number": t.turn_number, "question_text": t.question_text, "targets_gap": t.targets_gap}
        for t in scored
        if t.score["structure"] <= 2 or t.score["specificity"] <= 2 or t.score["relevance"] <= 2
    ]

    addressed_gaps = {t.targets_gap for t in scored if t.targets_gap and turn_avg(t) >= 3.5}
    all_gap_names = {g["skill"] for g in missing_skills if isinstance(g, dict) and "skill" in g}
    gap_coverage = {
        "addressed": sorted(addressed_gaps & all_gap_names),
        "still_open": sorted(all_gap_names - addressed_gaps),
    }

    return {
        "overall_score": overall_score,
        "strengths": strengths,
        "improvement_areas": improvement_areas,
        "gap_coverage": gap_coverage,
    }


@router.post("/{session_id}/complete", response_model=SessionReportResponse)
async def complete_interview(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    if session.status == "completed":
        raise ConflictError("Interview session is already completed")

    turns = await _get_turns(db, session_id)

    missing_skills: list = []
    if session.match_id is not None:
        match = (await db.execute(select(Match).where(Match.id == session.match_id))).scalar_one_or_none()
        if match is not None:
            missing_skills = match.missing_skills or []

    session.status = "completed"
    session.ended_at = datetime.now(UTC)

    aggregated = _aggregate_report(turns, missing_skills)
    report = SessionReport(session_id=session.id, **aggregated)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


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
