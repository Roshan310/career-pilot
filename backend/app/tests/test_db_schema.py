from sqlalchemy import select

from app.models.interview import InterviewSession, InterviewTurn, SessionReport
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.models.user import User


async def test_insert_and_read_one_row_per_model(db_session):
    user = User(email="smoke@example.com", password_hash="hashed")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(
        user_id=user.id,
        raw_text="Experienced engineer...",
        parsed_data={"skills": ["Python"]},
        embedding=[0.0] * 1536,
    )
    job = JobDescription(
        user_id=user.id,
        raw_text="We need a Python engineer",
        parsed_requirements={"required_skills": ["Python"]},
        embedding=[0.0] * 1536,
    )
    db_session.add_all([resume, job])
    await db_session.flush()

    match = Match(resume_id=resume.id, job_id=job.id, status="pending")
    db_session.add(match)
    await db_session.flush()

    session = InterviewSession(
        user_id=user.id, resume_id=resume.id, job_id=job.id, match_id=match.id
    )
    db_session.add(session)
    await db_session.flush()

    turn = InterviewTurn(
        session_id=session.id, turn_number=1, question_text="Tell me about X", question_type="main"
    )
    db_session.add(turn)
    await db_session.flush()

    report = SessionReport(session_id=session.id, overall_score=4.2)
    db_session.add(report)
    await db_session.commit()

    assert (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert (await db_session.execute(select(Resume).where(Resume.id == resume.id))).scalar_one()
    assert (await db_session.execute(select(JobDescription).where(JobDescription.id == job.id))).scalar_one()
    assert (await db_session.execute(select(Match).where(Match.id == match.id))).scalar_one()
    assert (
        await db_session.execute(select(InterviewSession).where(InterviewSession.id == session.id))
    ).scalar_one()
    assert (await db_session.execute(select(InterviewTurn).where(InterviewTurn.id == turn.id))).scalar_one()
    assert (await db_session.execute(select(SessionReport).where(SessionReport.id == report.id))).scalar_one()


async def test_deleting_resume_sets_interview_session_fk_null(db_session):
    user = User(email="fk-test@example.com", password_hash="hashed")
    db_session.add(user)
    await db_session.flush()

    resume = Resume(user_id=user.id, raw_text="text", parsed_data={})
    db_session.add(resume)
    await db_session.flush()

    session = InterviewSession(user_id=user.id, resume_id=resume.id)
    db_session.add(session)
    await db_session.commit()

    await db_session.delete(resume)
    await db_session.commit()

    # the in-memory `session` object predates the DB-level ON DELETE SET NULL
    # trigger firing, so force a re-read of its current row rather than trusting
    # the identity map's already-loaded (now stale) attributes.
    refreshed = (
        await db_session.execute(
            select(InterviewSession)
            .where(InterviewSession.id == session.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed.resume_id is None
