import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(subject: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: uuid.UUID) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )


def create_refresh_token(subject: uuid.UUID) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.jwt_refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    """Decode and validate a JWT, returning the user id in `sub`.

    Raises jwt.PyJWTError (expired/invalid signature/malformed) or ValueError
    (wrong token type / missing sub) — callers translate these to 401.
    """
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise ValueError(f"expected a {expected_type} token")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("token missing subject")
    return uuid.UUID(sub)
