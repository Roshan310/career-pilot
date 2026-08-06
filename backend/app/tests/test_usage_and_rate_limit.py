from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.db.session import get_db
from app.main import app
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.schemas.interview import QuestionPlan
from app.services.auth_service import issue_tokens, register_user

settings = get_settings()
EMBEDDING = [0.1] * 1536
CANNED_PLAN = QuestionPlan(
    questions=[{"question_text": f"Question {i}", "question_type": "main"} for i in range(1, 7)]
)


@pytest.fixture
async def resume_and_job(db_session):
    user = await register_user(db_session, "usageuser@example.com", "password123", None)
    resume = Resume(user_id=user.id, raw_text="x", parsed_data={"skills": []}, embedding=EMBEDDING)
    job = JobDescription(
        user_id=user.id, raw_text="x", parsed_requirements={"required_skills": []}, embedding=EMBEDDING
    )
    db_session.add_all([resume, job])
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job)
    return user, resume, job


@pytest.fixture
async def authed_client(db_session, resume_and_job):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user, _, _ = resume_and_job
    access_token, _ = issue_tokens(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {access_token}"
        yield client

    app.dependency_overrides.clear()


async def test_match_creation_blocked_past_free_tier_limit(authed_client, resume_and_job):
    _, resume, job = resume_and_job

    with patch("app.api.v1.matches.enqueue_matching_job") as mock_enqueue:
        for _ in range(settings.free_tier_monthly_match_limit):
            response = await authed_client.post(
                "/api/matches", json={"resume_id": str(resume.id), "job_id": str(job.id)}
            )
            assert response.status_code == 202

        over_limit_response = await authed_client.post(
            "/api/matches", json={"resume_id": str(resume.id), "job_id": str(job.id)}
        )

    assert over_limit_response.status_code == 429
    # no job enqueued for the rejected call — only the allowed ones
    assert mock_enqueue.call_count == settings.free_tier_monthly_match_limit


async def test_failed_question_generation_does_not_consume_an_interview(authed_client, resume_and_job):
    """Regression: the monthly interview count was incremented and committed
    *before* the 5-15s question-generation call. When that call failed — a Gemini
    429 being the common case — no session row was ever written, but the user had
    already been charged for it. Three failed starts and the free tier was gone
    without a single interview taken."""
    _, resume, job = resume_and_job
    payload = {"resume_id": str(resume.id), "job_id": str(job.id)}

    with patch(
        "app.services.interview_service.generate_question_plan",
        side_effect=LLMServiceError("LLM call failed. gemini: rate limited: 429 RESOURCE_EXHAUSTED"),
    ):
        response = await authed_client.post("/api/interviews", json=payload)

    assert response.status_code == 502
    assert (await authed_client.get("/api/usage")).json()["monthly_interview_count"] == 0

    # and the quota is genuinely still there to spend on a session that works
    with patch("app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN):
        assert (await authed_client.post("/api/interviews", json=payload)).status_code == 201

    assert (await authed_client.get("/api/usage")).json()["monthly_interview_count"] == 1


async def test_interview_creation_blocked_past_free_tier_limit(authed_client, resume_and_job):
    """The check still runs *before* the LLM call (SPECS.md §9): an over-limit
    request is rejected without spending a question-generation call."""
    _, resume, job = resume_and_job
    payload = {"resume_id": str(resume.id), "job_id": str(job.id)}

    with patch(
        "app.services.interview_service.generate_question_plan", return_value=CANNED_PLAN
    ) as mock_generate:
        for _ in range(settings.free_tier_monthly_interview_limit):
            assert (await authed_client.post("/api/interviews", json=payload)).status_code == 201

        over_limit_response = await authed_client.post("/api/interviews", json=payload)

    assert over_limit_response.status_code == 429
    assert mock_generate.call_count == settings.free_tier_monthly_interview_limit


async def test_usage_endpoint_reflects_match_count(authed_client, resume_and_job):
    _, resume, job = resume_and_job

    with patch("app.api.v1.matches.enqueue_matching_job"):
        await authed_client.post("/api/matches", json={"resume_id": str(resume.id), "job_id": str(job.id)})

    usage_response = await authed_client.get("/api/usage")
    body = usage_response.json()
    assert body["monthly_match_count"] == 1
    assert body["monthly_match_limit"] == settings.free_tier_monthly_match_limit
