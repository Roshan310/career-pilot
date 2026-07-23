import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

# HTTPBearer (not OAuth2PasswordBearer) — our endpoints take JSON bodies, not the
# OAuth2 form-encoded password grant, so we only need the `Authorization: Bearer`
# header extracted, not the full OAuth2 flow.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated")

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("Invalid or expired token")

    # lets rate_limit._rate_limit_key() key limits per-user for the rest of this request
    request.state.user = user
    return user
