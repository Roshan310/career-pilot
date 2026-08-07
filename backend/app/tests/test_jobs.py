from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.schemas.job import ParsedJobRequirements
from app.services.auth_service import issue_tokens, register_user

CANNED_REQUIREMENTS = ParsedJobRequirements(
    required_skills=["Python", "Kubernetes"],
    preferred_skills=["Terraform"],
    seniority_level="senior",
    years_experience_required=5,
    key_responsibilities=["Own infrastructure reliability"],
)
CANNED_EMBEDDING = [0.2] * 1536


@pytest.fixture
def mocked_llm_and_embeddings():
    with (
        patch("app.api.v1.jobs.parse_job", return_value=CANNED_REQUIREMENTS) as mock_parse,
        patch("app.api.v1.jobs.embed_text", return_value=CANNED_EMBEDDING) as mock_embed,
    ):
        yield mock_parse, mock_embed


@pytest.fixture
async def authed_client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user = await register_user(db_session, "jobuser@example.com", "password123", None)
    access_token, _ = issue_tokens(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {access_token}"
        yield client

    app.dependency_overrides.clear()


async def test_create_job_end_to_end(authed_client, mocked_llm_and_embeddings):
    mock_parse, mock_embed = mocked_llm_and_embeddings

    response = await authed_client.post(
        "/api/jobs",
        json={"title": "Backend Engineer", "company": "Acme", "raw_text": "We need a Python engineer"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Backend Engineer"
    assert body["parsed_requirements"]["required_skills"] == ["Python", "Kubernetes"]
    mock_parse.assert_called_once()
    mock_embed.assert_called_once()


async def test_list_and_get_job(authed_client, mocked_llm_and_embeddings):
    create_response = await authed_client.post(
        "/api/jobs", json={"title": "Backend Engineer", "raw_text": "We need a Python engineer"}
    )
    job_id = create_response.json()["id"]

    list_response = await authed_client.get("/api/jobs")
    assert len(list_response.json()) == 1

    get_response = await authed_client.get(f"/api/jobs/{job_id}")
    assert get_response.status_code == 200


async def test_get_job_not_owned_returns_404(authed_client, mocked_llm_and_embeddings, db_session):
    from app.models.job_description import JobDescription
    from app.services.auth_service import register_user as _register

    other_user = await _register(db_session, "otherjobuser@example.com", "password123", None)
    other_job = JobDescription(user_id=other_user.id, raw_text="secret jd", parsed_requirements={})
    db_session.add(other_job)
    await db_session.commit()
    await db_session.refresh(other_job)

    response = await authed_client.get(f"/api/jobs/{other_job.id}")
    assert response.status_code == 404


async def test_a_sub_year_experience_requirement_is_accepted(authed_client):
    """Regression: `years_experience_required` was `int`, so a JD asking for
    three months of experience produced 0.25 from the model and a 502 that no
    retry could clear — the job simply could not be saved."""
    parsed = ParsedJobRequirements(
        required_skills=["Python"],
        seniority_level="intern",
        years_experience_required=0.25,
    )

    with patch("app.api.v1.jobs.parse_job", return_value=parsed), \
         patch("app.api.v1.jobs.embed_text", return_value=CANNED_EMBEDDING):
        response = await authed_client.post(
            "/api/jobs", json={"title": "Intern", "raw_text": "3 months of Python experience required."}
        )

    assert response.status_code == 201, response.text
    assert response.json()["parsed_requirements"]["years_experience_required"] == 0.25
