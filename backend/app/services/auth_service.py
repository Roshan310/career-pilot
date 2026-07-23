import uuid

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User


async def register_user(db: AsyncSession, email: str, password: str, name: str | None) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A user with this email already exists")

    user = User(email=email, password_hash=hash_password(password), name=name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    return create_access_token(user.id), create_refresh_token(user.id)


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:
    try:
        user_id = decode_token(refresh_token, expected_type="refresh")
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired refresh token") from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("Invalid or expired refresh token")

    return create_access_token(user.id)
