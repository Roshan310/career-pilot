from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import UnprocessableError, UnsupportedFileTypeError
from app.main import app
from app.schemas.resume import ParsedResumeData
from app.services.auth_service import issue_tokens, register_user
from app.services.resume_parser import extract_text

FIXTURES = Path(__file__).parent / "fixtures"

CANNED_PARSED_DATA = ParsedResumeData(
    summary="Experienced Python engineer",
    skills=["Python", "FastAPI", "PostgreSQL"],
)
CANNED_EMBEDDING = [0.1] * 1536


@pytest.fixture
def mocked_llm_and_embeddings():
    with (
        patch("app.api.v1.resumes.parse_resume", return_value=CANNED_PARSED_DATA) as mock_parse,
        patch("app.api.v1.resumes.embed_text", return_value=CANNED_EMBEDDING) as mock_embed,
        patch("app.api.v1.resumes.storage_service.upload_file", return_value="resumes/fake-key"),
        patch("app.api.v1.resumes.storage_service.delete_file"),
    ):
        yield mock_parse, mock_embed


@pytest.fixture
async def authed_client(db_session):
    # main.py's dependency-injected `get_db` normally pulls from the app's own
    # engine (pointed at the dev DB) — override it to use the isolated test DB
    # session from conftest so this test never touches dev data.
    from app.db.session import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    user = await register_user(db_session, "resumeuser@example.com", "password123", None)
    access_token, _ = issue_tokens(user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {access_token}"
        yield client

    app.dependency_overrides.clear()


def test_extract_text_pdf():
    content = (FIXTURES / "sample_resume.pdf").read_bytes()
    text = extract_text("sample_resume.pdf", content)
    assert "Jane Doe" in text


def test_extract_text_docx():
    content = (FIXTURES / "sample_resume.docx").read_bytes()
    text = extract_text("sample_resume.docx", content)
    assert "Jane Doe" in text


def test_extract_text_txt():
    content = (FIXTURES / "sample_resume.txt").read_bytes()
    text = extract_text("sample_resume.txt", content)
    assert "Jane Doe" in text


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("resume.exe", b"not a resume")


def test_extract_text_rejects_empty_pdf():
    content = (FIXTURES / "blank_resume.pdf").read_bytes()
    with pytest.raises(UnprocessableError):
        extract_text("blank.pdf", content)


async def test_upload_resume_end_to_end(authed_client, mocked_llm_and_embeddings):
    mock_parse, mock_embed = mocked_llm_and_embeddings
    content = (FIXTURES / "sample_resume.txt").read_bytes()

    response = await authed_client.post(
        "/api/resumes",
        files={"file": ("sample_resume.txt", content, "text/plain")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["file_name"] == "sample_resume.txt"
    assert body["parsed_data"]["skills"] == ["Python", "FastAPI", "PostgreSQL"]
    assert body["version"] == 1
    mock_parse.assert_called_once()
    mock_embed.assert_called_once()


async def test_upload_resume_rejects_oversized_file(authed_client, mocked_llm_and_embeddings):
    from app.core.config import get_settings

    settings = get_settings()
    oversized = b"x" * (settings.max_resume_file_size_mb * 1024 * 1024 + 1)

    response = await authed_client.post(
        "/api/resumes", files={"file": ("big.txt", oversized, "text/plain")}
    )
    assert response.status_code == 422


async def test_list_get_delete_resume(authed_client, mocked_llm_and_embeddings):
    content = (FIXTURES / "sample_resume.txt").read_bytes()
    upload_response = await authed_client.post(
        "/api/resumes", files={"file": ("sample_resume.txt", content, "text/plain")}
    )
    resume_id = upload_response.json()["id"]

    list_response = await authed_client.get("/api/resumes")
    assert len(list_response.json()) == 1

    get_response = await authed_client.get(f"/api/resumes/{resume_id}")
    assert get_response.status_code == 200

    delete_response = await authed_client.delete(f"/api/resumes/{resume_id}")
    assert delete_response.status_code == 204

    get_after_delete = await authed_client.get(f"/api/resumes/{resume_id}")
    assert get_after_delete.status_code == 404


async def test_get_resume_not_owned_by_user_returns_404(authed_client, mocked_llm_and_embeddings, db_session):
    other_user = await register_user(db_session, "otheruser@example.com", "password123", None)
    from app.models.resume import Resume

    other_resume = Resume(user_id=other_user.id, raw_text="secret", parsed_data={})
    db_session.add(other_resume)
    await db_session.commit()
    await db_session.refresh(other_resume)

    response = await authed_client.get(f"/api/resumes/{other_resume.id}")
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Downloading the original file
#
# file_url was written on upload and, until now, read only in order to delete
# it — the file the user handed us was unreachable to them.
# --------------------------------------------------------------------------


async def _upload(client, filename: str) -> dict:
    """Upload under an arbitrary filename.

    Text extraction is patched out because these tests are about serving the
    stored bytes back, not about parsing — a .pdf name carrying text really does
    (correctly) fail in pdfplumber.
    """
    content = (FIXTURES / "sample_resume.txt").read_bytes()
    with patch("app.api.v1.resumes.extract_text", return_value="Experienced Python engineer"):
        response = await client.post(
            "/api/resumes", files={"file": (filename, content, "application/octet-stream")}
        )
    assert response.status_code == 201, response.text
    return response.json()


async def test_download_returns_the_stored_file(authed_client, mocked_llm_and_embeddings):
    created = await _upload(authed_client, filename="my-cv.pdf")

    with patch("app.services.storage_service.get_bytes", return_value=b"%PDF-1.4 fake"):
        response = await authed_client.get(f"/api/resumes/{created['id']}/file")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake"
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="my-cv.pdf"' in response.headers["content-disposition"]


async def test_download_infers_the_type_from_the_extension(authed_client, mocked_llm_and_embeddings):
    """There is no stored content type — it comes from the sanitised filename."""
    created = await _upload(authed_client, filename="notes.txt")

    with patch("app.services.storage_service.get_bytes", return_value=b"plain"):
        response = await authed_client.get(f"/api/resumes/{created['id']}/file")

    assert response.headers["content-type"].startswith("text/plain")


async def test_download_404s_when_the_object_is_gone(authed_client, mocked_llm_and_embeddings):
    """The row can outlive the object if a delete half-failed. That's a 404, not
    a 500 with an empty body."""
    created = await _upload(authed_client, filename="gone.pdf")

    with patch("app.services.storage_service.get_bytes", return_value=None):
        response = await authed_client.get(f"/api/resumes/{created['id']}/file")

    assert response.status_code == 404


async def test_download_requires_ownership(authed_client, mocked_llm_and_embeddings, db_session):
    created = await _upload(authed_client, filename="private.pdf")

    other = await register_user(db_session, "nosy@example.com", "password123", None)
    token, _ = issue_tokens(other)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as intruder:
        intruder.headers["Authorization"] = f"Bearer {token}"
        with patch("app.services.storage_service.get_bytes", return_value=b"secret"):
            assert (await intruder.get(f"/api/resumes/{created['id']}/file")).status_code == 404
