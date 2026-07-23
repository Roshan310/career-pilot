from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.models.job_description import JobDescription
from app.models.match import Match
from app.models.resume import Resume
from app.services.auth_service import issue_tokens, register_user
from app.workers.jobs import compute_match

EMBEDDING = [0.1] * 1536


@pytest.fixture
async def resume_and_job(db_session):
    user = await register_user(db_session, "matchuser@example.com", "password123", None)

    resume = Resume(
        user_id=user.id,
        raw_text="Experienced Python engineer with Kubernetes exposure",
        parsed_data={"skills": ["Python", "Kubernetes"], "experience": []},
        embedding=EMBEDDING,
    )
    job = JobDescription(
        user_id=user.id,
        raw_text="Looking for a Python engineer with Kubernetes",
        parsed_requirements={"required_skills": ["Python", "Kubernetes"], "preferred_skills": []},
        embedding=EMBEDDING,
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


async def test_compute_match_scores_and_completes(db_session, resume_and_job):
    _, resume, job = resume_and_job
    match = Match(resume_id=resume.id, job_id=job.id, status="pending")
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(match)

    with patch(
        "app.workers.jobs.generate_suggestions",
        return_value=[{"missing_skill": "x", "suggestion": "y"}],
    ):
        await compute_match(db_session, match.id)

    await db_session.refresh(match)
    assert match.status == "done"
    assert match.overall_score == 1.0  # identical embeddings, full skill overlap, no experience requirement
    assert match.suggestions == [{"missing_skill": "x", "suggestion": "y"}]


async def test_compute_match_degrades_gracefully_when_suggestions_fail(db_session, resume_and_job):
    _, resume, job = resume_and_job
    match = Match(resume_id=resume.id, job_id=job.id, status="pending")
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(match)

    with patch("app.workers.jobs.generate_suggestions", side_effect=RuntimeError("LLM down")):
        await compute_match(db_session, match.id)

    await db_session.refresh(match)
    # scoring succeeded, so the match is still "done" with an empty suggestions
    # list — not "failed" — per §9's "skip scoring detail rather than fail the whole thing"
    assert match.status == "done"
    assert match.suggestions == []
    assert match.overall_score is not None


async def test_compute_match_fails_when_embedding_missing(db_session, resume_and_job):
    _, resume, job = resume_and_job
    resume.embedding = None
    await db_session.commit()

    match = Match(resume_id=resume.id, job_id=job.id, status="pending")
    db_session.add(match)
    await db_session.commit()
    await db_session.refresh(match)

    await compute_match(db_session, match.id)

    await db_session.refresh(match)
    assert match.status == "failed"
    assert match.error_message is not None


async def test_create_match_enqueues_job_and_returns_pending(authed_client, resume_and_job):
    _, resume, job = resume_and_job

    with patch("app.api.v1.matches.enqueue_matching_job") as mock_enqueue:
        response = await authed_client.post(
            "/api/matches", json={"resume_id": str(resume.id), "job_id": str(job.id)}
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    mock_enqueue.assert_called_once_with(body["id"])


async def test_create_match_unknown_resume_returns_404(authed_client, resume_and_job):
    _, _, job = resume_and_job
    response = await authed_client.post(
        "/api/matches",
        json={"resume_id": "00000000-0000-0000-0000-000000000000", "job_id": str(job.id)},
    )
    assert response.status_code == 404


async def test_get_match_not_owned_returns_404(authed_client, resume_and_job, db_session):
    _, resume, job = resume_and_job
    other_user = await register_user(db_session, "otherresumeuser@example.com", "password123", None)
    other_resume = Resume(user_id=other_user.id, raw_text="x", parsed_data={}, embedding=EMBEDDING)
    db_session.add(other_resume)
    await db_session.commit()
    await db_session.refresh(other_resume)

    other_match = Match(resume_id=other_resume.id, job_id=job.id, status="done")
    db_session.add(other_match)
    await db_session.commit()
    await db_session.refresh(other_match)

    response = await authed_client.get(f"/api/matches/{other_match.id}")
    assert response.status_code == 404
