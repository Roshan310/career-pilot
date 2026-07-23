from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings


def _rate_limit_key(request: Request) -> str:
    """Key rate limits off the authenticated user when known, else client IP."""
    user = getattr(request.state, "user", None)
    if user is not None:
        return f"user:{user.id}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key, storage_uri=get_settings().redis_url)
