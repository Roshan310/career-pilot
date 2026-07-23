import jwt
import pytest

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.services.auth_service import (
    authenticate_user,
    issue_tokens,
    refresh_access_token,
    register_user,
)

settings = get_settings()


async def test_register_then_duplicate_email_conflicts(db_session):
    await register_user(db_session, "dup@example.com", "password123", "Name")
    with pytest.raises(ConflictError):
        await register_user(db_session, "dup@example.com", "password123", "Name")


async def test_register_hashes_password_not_stored_plaintext(db_session):
    user = await register_user(db_session, "hash@example.com", "password123", None)
    assert user.password_hash != "password123"


async def test_login_wrong_password_raises_unauthorized(db_session):
    await register_user(db_session, "wrongpw@example.com", "correct-password", None)
    with pytest.raises(UnauthorizedError):
        await authenticate_user(db_session, "wrongpw@example.com", "incorrect-password")


async def test_login_unknown_email_raises_unauthorized(db_session):
    with pytest.raises(UnauthorizedError):
        await authenticate_user(db_session, "nobody@example.com", "whatever")


async def test_login_correct_password_returns_user(db_session):
    registered = await register_user(db_session, "ok@example.com", "password123", None)
    authenticated = await authenticate_user(db_session, "ok@example.com", "password123")
    assert authenticated.id == registered.id


async def test_issued_access_token_carries_correct_type_and_subject(db_session):
    user = await register_user(db_session, "tok@example.com", "password123", None)
    access_token, refresh_token = issue_tokens(user)

    access_payload = jwt.decode(
        access_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    refresh_payload = jwt.decode(
        refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == str(user.id)


async def test_expired_access_token_is_rejected(db_session):
    import datetime

    user = await register_user(db_session, "expired@example.com", "password123", None)
    expired_payload = {
        "sub": str(user.id),
        "type": "access",
        "iat": datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2),
        "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


async def test_refresh_token_cannot_be_used_as_access_token(db_session):
    from app.core.security import decode_token

    user = await register_user(db_session, "swap@example.com", "password123", None)
    _, refresh_token = issue_tokens(user)

    with pytest.raises(ValueError):
        decode_token(refresh_token, expected_type="access")


async def test_refresh_access_token_issues_new_access_token(db_session):
    user = await register_user(db_session, "refresh@example.com", "password123", None)
    _, refresh_token = issue_tokens(user)

    new_access_token = await refresh_access_token(db_session, refresh_token)
    payload = jwt.decode(new_access_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"


async def test_refresh_with_garbage_token_raises_unauthorized(db_session):
    with pytest.raises(UnauthorizedError):
        await refresh_access_token(db_session, "not-a-real-token")
