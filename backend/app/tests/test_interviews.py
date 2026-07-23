from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.interview import QuestionPlan
from app.services.auth_service import issue_tokens, register_user

settings = get_settings()
EMBEDDING = [0.1] * 1536

QUESTIONS = [
    {"question_text": f"Question {i}", "question_type": "main", "targets_gap": f"gap-{i}", "based_on": f"bullet {i}"}
    for i in range(1, 7)
]
CANNED_PLAN = QuestionPlan(questions=QUESTIONS)


@pytest.fixture
async def resume_job_match(db_session):
    user = await register_user(db_session, "interviewuser@example.com", "password123", None)
    resume = Resume(
        user_id=user.id,
        raw_text="Experienced Python engineer",
        parsed_data={"skills": ["Python"], "experience": []},
        embedding=EMBEDDING,
    )
    job = JobDescription(
        user_id=user.id,
        raw_text="Need a Python engineer",
        parsed_requirements={"required_skills": ["Python"]},
        embedding=EMBEDDING,
    )
    db_session.add_all([resume, job])
    await db_session.flush()
    match = Match(
        resume_id=resume.id,
        job_id=job.id,
        status="done",
        missing_skills=[{"skill": "gap-1", "priority": "required"}],
    )
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job)
    await db_session.refresh(match)
    return user, resume, job, match


@pytest.fixture
async def authed_client(db_session, resume_job_match):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user, _, _, _ = resume_job_match
    access_token, _ = issue_tokens(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {access_token}"
        yield client

    app.dependency_overrides.clear()


def _create_interview_payload(resume, job, match):
    return {"resume_id": str(resume.id), "job_id": str(job.id), "match_id": str(match.id)}


async def test_create_interview_generates_question_plan_and_first_question(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.api.v1.interviews.generate_question_plan", return_value=CANNED_PLAN):
        response = await authed_client.post("/api/interviews", json=_create_interview_payload(resume, job, match))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "in_progress"
    assert len(body["question_plan"]) == 6
    assert body["current_question"]["turn_number"] == 1
    assert body["current_question"]["question_text"] == "Question 1"


def _good_evaluation(**overrides):
    base = {"structure": 5, "specificity": 5, "relevance": 5, "next_action": "next_question", "follow_up_question": None}
    base.update(overrides)
    return base


async def test_well_answered_session_completes_without_followups(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.api.v1.interviews.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    with patch("app.api.v1.interviews.evaluate_answer") as mock_eval:
        from app.services.llm.answer_evaluation import AnswerEvaluation

        mock_eval.return_value = AnswerEvaluation(**_good_evaluation())

        question_number = 1
        session_status = "in_progress"
        turns_answered = 0
        while session_status == "in_progress" and turns_answered < 10:
            response = await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={"question_number": question_number, "answer_transcript": "A great STAR answer.", "duration": 30.0},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            session_status = body["session_status"]
            turns_answered += 1
            if body["next_question"]:
                question_number = body["next_question"]["turn_number"]

    assert session_status == "wrapping_up"
    assert turns_answered == len(QUESTIONS)  # exactly 6 main questions, zero follow-ups

    complete_response = await authed_client.post(f"/api/interviews/{session_id}/complete")
    assert complete_response.status_code == 200, complete_response.text
    report = complete_response.json()
    assert report["overall_score"] == 5.0
    assert len(report["strengths"]) == len(QUESTIONS)
    assert report["improvement_areas"] == []


async def test_forced_followup_caps_at_max_then_advances(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.api.v1.interviews.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    from app.services.llm.answer_evaluation import AnswerEvaluation

    # Always tells the state machine to ask a follow-up — the cap must still hold.
    always_follow_up = AnswerEvaluation(
        structure=2, specificity=2, relevance=2, next_action="follow_up", follow_up_question="Can you say more?"
    )

    with patch("app.api.v1.interviews.evaluate_answer", return_value=always_follow_up):
        response = await authed_client.post(
            f"/api/interviews/{session_id}/turns",
            json={"question_number": 1, "answer_transcript": "vague answer", "duration": 10.0},
        )
        assert response.json()["next_question"]["question_type"] == "follow_up"

        followup_count = 0
        question_number = response.json()["next_question"]["turn_number"]
        for _ in range(settings.interview_max_followups_per_question + 2):
            resp = await authed_client.post(
                f"/api/interviews/{session_id}/turns",
                json={"question_number": question_number, "answer_transcript": "still vague", "duration": 10.0},
            )
            body = resp.json()
            if body["next_question"] and body["next_question"]["question_type"] == "follow_up":
                followup_count += 1
                question_number = body["next_question"]["turn_number"]
            else:
                break

        assert followup_count == settings.interview_max_followups_per_question - 1
        # after the cap, the next question served must be "Question 2" (advance), not another follow-up
        assert body["next_question"]["question_text"] == "Question 2"


async def test_mismatched_question_number_returns_conflict(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.api.v1.interviews.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    response = await authed_client.post(
        f"/api/interviews/{session_id}/turns",
        json={"question_number": 99, "answer_transcript": "wrong turn", "duration": 5.0},
    )
    assert response.status_code == 409


async def test_get_interview_report_before_completion_returns_404(authed_client, resume_job_match):
    _, resume, job, match = resume_job_match
    with patch("app.api.v1.interviews.generate_question_plan", return_value=CANNED_PLAN):
        create_response = await authed_client.post(
            "/api/interviews", json=_create_interview_payload(resume, job, match)
        )
    session_id = create_response.json()["id"]

    response = await authed_client.get(f"/api/interviews/{session_id}/report")
    assert response.status_code == 404
