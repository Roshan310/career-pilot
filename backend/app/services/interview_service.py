"""Transport-agnostic interview orchestration.

This is the seam that keeps the voice layer swappable. Today the only caller is
the HTTP router (`api/v1/interviews.py`), which receives a transcript the browser
produced with the Web Speech API. When that is replaced by server-side streaming
STT (Deepgram / Gemini Live), the new transport — a WebSocket endpoint — becomes
a *sibling* of that router: it runs STT, builds the same `TurnSubmitRequest`
envelope, and calls the same `submit_answer()` below. The state machine,
evaluation, scoring and report aggregation don't move.

Ownership checks stay in the router (per AGENT.md's convention); everything that
must hold regardless of transport — session status, turn sequencing, the skip
path, the caps — lives here.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.interview import InterviewSession, InterviewTurn, SessionReport
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import (
    CurrentQuestion,
    InterviewSessionResponse,
    SessionProgress,
    TurnDetail,
    TurnSubmitRequest,
    TurnSubmitResponse,
)
from app.services import interview_state_machine as sm
from app.services.llm.answer_evaluation import evaluate_answer
from app.services.llm.question_generation import generate_question_plan
from app.services.report_findings import (
    build_findings,
    dimension_averages,
    turn_average,
    turn_weight,
)
from app.services.speech_metrics import aggregate_speech_metrics, compute_speech_metrics

logger = logging.getLogger(__name__)

# Statuses that still accept answers vs. are finished. Kept here (not scattered
# across call sites) so a second transport can't drift from these rules.
ACTIVE_STATUSES = ("in_progress",)
FINALIZABLE_STATUSES = ("in_progress", "wrapping_up")


async def get_turns(db: AsyncSession, session_id: uuid.UUID) -> list[InterviewTurn]:
    result = await db.execute(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_number)
    )
    return list(result.scalars().all())


async def get_turn(db: AsyncSession, session_id: uuid.UUID, turn_number: int) -> InterviewTurn | None:
    result = await db.execute(
        select(InterviewTurn).where(
            InterviewTurn.session_id == session_id, InterviewTurn.turn_number == turn_number
        )
    )
    return result.scalar_one_or_none()


def pending_question(turns: list[InterviewTurn]) -> CurrentQuestion | None:
    """The one turn that has a question but no answer yet. Turns are pre-created
    with the answer fields NULL, so 'where is the interview' is a lookup rather
    than a replay of the whole session."""
    for turn in turns:
        if turn.answer_transcript is None:
            return CurrentQuestion(
                turn_number=turn.turn_number,
                question_text=turn.question_text,
                question_type=turn.question_type,
                targets_gap=turn.targets_gap,
            )
    return None


def _progress(session: InterviewSession, turns: list[InterviewTurn]) -> SessionProgress:
    return SessionProgress(**sm.session_progress(session, turns, session.question_plan or []))


async def build_session_response(
    db: AsyncSession, session: InterviewSession
) -> InterviewSessionResponse:
    turns = await get_turns(db, session.id)
    response = InterviewSessionResponse.model_validate(session)
    response.current_question = pending_question(turns)
    response.turns = [TurnDetail.model_validate(t) for t in turns]
    response.progress = _progress(session, turns)
    return response


async def start_session(
    db: AsyncSession,
    user: User,
    resume: Resume,
    job: JobDescription,
    match: Match | None,
    mode: str,
) -> InterviewSession:
    """Generate the question plan and open the session. Synchronous on purpose —
    see docs/decisions.md: the 5-15s LLM call is covered by a 'preparing your
    interview' screen rather than a second RQ job type."""
    missing_skills = (match.missing_skills or []) if match is not None else []

    # Synchronous to *this request*, but off the event loop. `generate_question_plan`
    # is a blocking 5-15s HTTP call; run inline it froze every other request in
    # the worker for the duration, so one person starting an interview stalled
    # everyone else's page loads.
    question_plan = await asyncio.to_thread(
        generate_question_plan, resume.parsed_data, job.parsed_requirements, missing_skills
    )

    session = InterviewSession(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        match_id=match.id if match is not None else None,
        mode=mode,
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
    return session


async def submit_answer(
    db: AsyncSession, session: InterviewSession, submission: TurnSubmitRequest
) -> TurnSubmitResponse:
    """Record an answer, evaluate it, and let the state machine decide what's next.

    `submission` is the provider-agnostic envelope — whether the transcript came
    from the browser, a typed fallback, or (later) server-side STT only shows up
    as `submission.source`, which is recorded on the metrics and otherwise
    ignored by everything downstream.
    """
    if session.status not in ACTIVE_STATUSES:
        raise ConflictError(f"Interview session is '{session.status}', not accepting answers")

    turns = await get_turns(db, session.id)
    pending = pending_question(turns)
    if pending is None or pending.turn_number != submission.question_number:
        raise ConflictError(
            f"Expected an answer for question {pending.turn_number if pending else 'none pending'}, "
            f"got {submission.question_number}"
        )

    turn = next(t for t in turns if t.turn_number == submission.question_number)
    transcript = submission.answer_transcript.strip()
    # §7.2: nothing was captured after the retry prompt. Store "" (not NULL) so the
    # turn still counts as answered and the interview advances.
    is_skipped = submission.skipped or not transcript

    turn.answer_transcript = "" if is_skipped else submission.answer_transcript
    turn.answer_duration_seconds = submission.duration
    turn.speech_metrics = compute_speech_metrics(
        turn.answer_transcript, submission.duration, submission.segments, submission.source
    )

    if is_skipped:
        # No LLM call for silence — there is nothing to score, and paying for the
        # round trip would only slow the live loop down.
        turn.score = None
        llm_next_action, llm_follow_up = "next_question", None
    else:
        based_on = turn.targets_gap or turn.question_text
        try:
            # Off the event loop: this runs on every single answer, and a blocking
            # LLM round trip here stalls every other in-flight request.
            evaluation = await asyncio.to_thread(
                evaluate_answer, turn.question_text, based_on, submission.answer_transcript
            )
            turn.score = {
                "structure": evaluation.structure,
                "specificity": evaluation.specificity,
                "relevance": evaluation.relevance,
            }
            llm_next_action, llm_follow_up = evaluation.next_action, evaluation.follow_up_question
        except Exception:
            # graceful degradation (§9): scoring this turn failed, but the
            # interview keeps moving rather than the whole request failing.
            #
            # Logged with the traceback because this catches everything: a Gemini
            # outage and a TypeError in our own scoring code produce an identical
            # user experience, and without this line they were indistinguishable
            # in the logs too.
            logger.warning(
                "Answer evaluation failed for session %s turn %s; continuing unscored",
                session.id,
                turn.turn_number,
                exc_info=True,
            )
            turn.score = None
            llm_next_action, llm_follow_up = "next_question", None

    await db.flush()
    turns = await get_turns(db, session.id)  # refresh with the now-answered turn included

    next_step = sm.decide_next_step(
        session, turns, session.question_plan or [], turn, llm_next_action, llm_follow_up
    )

    if next_step["action"] == "wrap_up":
        # Persist it, not just report it: a client that reconnects has to be able
        # to tell "wrap up now" from "still going".
        session.status = "wrapping_up"
        await db.commit()
        return TurnSubmitResponse(
            session_status=session.status,
            evaluation=turn.score,
            next_question=None,
            speech_metrics=turn.speech_metrics,
            progress=_progress(session, turns),
        )

    next_turn = InterviewTurn(
        session_id=session.id,
        turn_number=submission.question_number + 1,
        question_text=next_step["question_text"],
        question_type=next_step["question_type"],
        targets_gap=next_step.get("targets_gap"),
    )
    db.add(next_turn)
    await db.commit()

    return TurnSubmitResponse(
        session_status=session.status,
        evaluation=turn.score,
        next_question=CurrentQuestion(
            turn_number=next_turn.turn_number,
            question_text=next_turn.question_text,
            question_type=next_turn.question_type,
            targets_gap=next_turn.targets_gap,
        ),
        speech_metrics=turn.speech_metrics,
        progress=_progress(session, turns),
    )


def aggregate_report(turns: list[InterviewTurn], missing_skills: list[dict]) -> dict:
    """SPECS.md §7.5 — deterministic aggregation, not an LLM call."""
    # `score` is JSONB, so the database guarantees nothing about its shape.
    # `turn_average` returns None for a row with no usable dimension instead of
    # indexing blindly — the previous `s["structure"] + ...` raised straight out
    # of POST /complete, losing the whole report over one malformed row.
    # Weighting and averaging are imported rather than reimplemented so the
    # headline score and the dimension averages can never disagree.
    averages = {t.turn_number: avg for t in turns if (avg := turn_average(t)) is not None}
    scored = [t for t in turns if t.answer_transcript is not None and t.turn_number in averages]

    weighted_sum = sum(averages[t.turn_number] * turn_weight(t) for t in scored)
    weight_total = sum(turn_weight(t) for t in scored)
    overall_score = (weighted_sum / weight_total) if weight_total else None

    addressed_gaps = {
        t.targets_gap for t in scored if t.targets_gap and averages[t.turn_number] >= 3.5
    }
    all_gap_names = {g["skill"] for g in missing_skills if isinstance(g, dict) and "skill" in g}
    gap_coverage = {
        "addressed": sorted(addressed_gaps & all_gap_names),
        "still_open": sorted(all_gap_names - addressed_gaps),
    }

    return {
        "overall_score": overall_score,
        # Strengths and improvement areas are patterns across the whole session
        # rather than a list of questions — see report_findings.py. Kept in its
        # own module so the backfill script can re-derive them without importing
        # the LLM layer, and so it can never accidentally recompute gap_coverage
        # (which depends on the match, not on the turns).
        **build_findings(turns),
        # Stored, not derived on read: the findings only mention a dimension when
        # it qualified as a strength or weakness, so a flat 3.0/3.0/3.0 session
        # would otherwise leave no trace to plot.
        "dimension_averages": dimension_averages(turns),
        "gap_coverage": gap_coverage,
        # Rolled up over every turn with measurable speech, including ones the
        # LLM couldn't score — delivery is measurable even when content isn't.
        "speech_metrics": aggregate_speech_metrics([t.speech_metrics for t in turns]),
    }


async def get_report(db: AsyncSession, session_id: uuid.UUID) -> SessionReport | None:
    return (
        await db.execute(select(SessionReport).where(SessionReport.session_id == session_id))
    ).scalar_one_or_none()


async def complete_session(db: AsyncSession, session: InterviewSession) -> SessionReport:
    # Idempotent by design. A double-click, a client retry after a dropped
    # response, or two tabs finishing at once all arrive here; returning the
    # report that already exists is the honest answer to "complete this", and it
    # is what keeps the unique constraint on session_id from surfacing as a 500.
    if session.status == "completed":
        existing = await get_report(db, session.id)
        if existing is not None:
            return existing

    if session.status not in FINALIZABLE_STATUSES:
        raise ConflictError(f"Interview session is '{session.status}', it cannot be completed")

    turns = await get_turns(db, session.id)

    missing_skills: list = []
    if session.match_id is not None:
        match = (await db.execute(select(Match).where(Match.id == session.match_id))).scalar_one_or_none()
        if match is not None:
            missing_skills = match.missing_skills or []

    session.status = "completed"
    session.ended_at = datetime.now(UTC)

    report = SessionReport(session_id=session.id, **aggregate_report(turns, missing_skills))
    db.add(report)
    try:
        await db.commit()
    except IntegrityError:
        # Lost the race to a concurrent complete. The unique constraint on
        # session_id is doing its job; the other request's report is equally
        # valid, so hand that one back rather than failing a request the user
        # experiences as "finish my interview".
        await db.rollback()
        existing = await get_report(db, session.id)
        if existing is None:
            raise
        logger.info("Concurrent complete for session %s; returning existing report", session.id)
        return existing
    await db.refresh(report)
    return report


async def abandon_session(db: AsyncSession, session: InterviewSession) -> InterviewSession:
    """End a session without producing a report — the candidate walked away or
    quit early. Distinct from 'completed' so interview history doesn't show a
    half-finished run as a real result."""
    if session.status not in FINALIZABLE_STATUSES:
        raise ConflictError(f"Interview session is '{session.status}', it cannot be abandoned")

    session.status = "abandoned"
    session.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return session
