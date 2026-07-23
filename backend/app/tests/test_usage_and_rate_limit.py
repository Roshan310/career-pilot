from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.job_description import JobDescription
from app.models.resume import Resume
from app.services.auth_service import issue_tokens, register_user

settings = get_settings()
EMBEDDING = [0.1] * 1536


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


async def test_usage_endpoint_reflects_match_count(authed_client, resume_and_job):
    _, resume, job = resume_and_job

    with patch("app.api.v1.matches.enqueue_matching_job"):
        await authed_client.post("/api/matches", json={"resume_id": str(resume.id), "job_id": str(job.id)})

    usage_response = await authed_client.get("/api/usage")
    body = usage_response.json()
    assert body["monthly_match_count"] == 1
    assert body["monthly_match_limit"] == settings.free_tier_monthly_match_limit
