import uuid
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


# --------------------------------------------------------------------------
# Application tracking
#
# job_descriptions was a write-once record: no PATCH, no DELETE, so a typo'd
# title was permanent and there was nothing to come back and update.
# --------------------------------------------------------------------------


async def _create_job(client, **overrides) -> dict:
    payload = {"title": "Backend Engineer", "company": "Acme", "raw_text": "We need a Python engineer"}
    payload.update(overrides)
    response = await client.post("/api/jobs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_new_job_starts_in_the_saved_state(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)
    assert job["status"] == "saved"
    assert job["priority"] == "normal"
    assert job["applied_at"] is None


async def test_moving_a_job_through_the_pipeline(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)

    response = await authed_client.patch(
        f"/api/jobs/{job['id']}",
        json={"status": "applied", "applied_at": "2026-08-01", "notes": "Referred by Sam"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "applied"
    assert body["applied_at"] == "2026-08-01"
    assert body["notes"] == "Referred by Sam"
    # Untouched fields survive a PATCH.
    assert body["title"] == "Backend Engineer"
    assert body["priority"] == "normal"


async def test_patch_can_clear_a_field(authed_client, mocked_llm_and_embeddings):
    """None is a real value here. `exclude_unset`, not `exclude_none` — otherwise
    a deadline could be set but never removed."""
    job = await _create_job(authed_client)
    await authed_client.patch(f"/api/jobs/{job['id']}", json={"deadline": "2026-09-30"})

    cleared = await authed_client.patch(f"/api/jobs/{job['id']}", json={"deadline": None})

    assert cleared.status_code == 200
    assert cleared.json()["deadline"] is None


async def test_patch_leaves_omitted_fields_alone(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)
    await authed_client.patch(f"/api/jobs/{job['id']}", json={"notes": "keep me"})

    response = await authed_client.patch(f"/api/jobs/{job['id']}", json={"status": "screening"})

    assert response.json()["notes"] == "keep me"


async def test_patch_rejects_a_status_outside_the_pipeline(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)
    response = await authed_client.patch(f"/api/jobs/{job['id']}", json={"status": "ghosted"})
    assert response.status_code == 422


async def test_patch_does_not_re_parse_the_posting(authed_client, mocked_llm_and_embeddings):
    """A status change must not spend an LLM call, and editing the label must not
    invalidate matches already computed against this job."""
    mock_parse, mock_embed = mocked_llm_and_embeddings
    job = await _create_job(authed_client)
    calls_after_create = (mock_parse.call_count, mock_embed.call_count)

    await authed_client.patch(f"/api/jobs/{job['id']}", json={"status": "applied", "title": "Fixed Title"})

    assert (mock_parse.call_count, mock_embed.call_count) == calls_after_create


async def test_updated_at_moves_on_a_patch(authed_client, mocked_llm_and_embeddings):
    """The list is ordered by updated_at so a status change floats the job up."""
    job = await _create_job(authed_client)
    before = job["updated_at"]

    after = (await authed_client.patch(f"/api/jobs/{job['id']}", json={"status": "applied"})).json()

    assert after["updated_at"] >= before


async def test_deleting_a_job_removes_it(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)

    assert (await authed_client.delete(f"/api/jobs/{job['id']}")).status_code == 204
    assert (await authed_client.get(f"/api/jobs/{job['id']}")).status_code == 404


async def test_deleting_a_job_takes_its_matches_with_it(
    authed_client, mocked_llm_and_embeddings, db_session
):
    """matches.job_id is ON DELETE CASCADE. The UI warns about this; if the
    cascade ever changed, that warning would become a lie."""
    from sqlalchemy import select

    from app.models.match import Match
    from app.models.resume import Resume
    from app.models.user import User

    job = await _create_job(authed_client)

    user = (await db_session.execute(select(User))).scalars().first()
    resume = Resume(
        user_id=user.id, raw_text="x", parsed_data={"skills": []}, embedding=[0.1] * 1536
    )
    db_session.add(resume)
    await db_session.commit()

    match = Match(resume_id=resume.id, job_id=uuid.UUID(job["id"]), status="done")
    db_session.add(match)
    await db_session.commit()
    match_id = match.id

    await authed_client.delete(f"/api/jobs/{job['id']}")

    survivor = (await db_session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    assert survivor is None, "match should have been cascaded away with its job"


async def test_tracking_endpoints_require_ownership(authed_client, mocked_llm_and_embeddings, db_session):
    job = await _create_job(authed_client)

    other = await register_user(db_session, "intruder@example.com", "password123", None)
    other_token, _ = issue_tokens(other)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as intruder:
        intruder.headers["Authorization"] = f"Bearer {other_token}"
        assert (await intruder.patch(f"/api/jobs/{job['id']}", json={"status": "offer"})).status_code == 404
        assert (await intruder.delete(f"/api/jobs/{job['id']}")).status_code == 404

    # and it really is untouched
    assert (await authed_client.get(f"/api/jobs/{job['id']}")).json()["status"] == "saved"


async def test_the_list_exposes_tracking_state(authed_client, mocked_llm_and_embeddings):
    job = await _create_job(authed_client)
    await authed_client.patch(f"/api/jobs/{job['id']}", json={"status": "interviewing", "priority": "high"})

    rows = (await authed_client.get("/api/jobs")).json()

    row = next(r for r in rows if r["id"] == job["id"])
    assert row["status"] == "interviewing"
    assert row["priority"] == "high"
