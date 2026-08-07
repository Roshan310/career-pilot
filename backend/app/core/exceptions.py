import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application errors that map to a specific HTTP status."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class UnprocessableError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class UsageLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class UnsupportedFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class LLMServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY


class LLMConfigurationError(LLMServiceError):
    """The model provider is misconfigured — wrong model name, bad key.

    A subclass of LLMServiceError so existing handling still catches it, but
    distinguishable so callers stop telling the user to "try again": no number
    of retries fixes a model that does not exist.
    """


class ServiceUnavailableError(AppError):
    """A dependency we own is down — Redis, object storage, the TTS vendor.

    Distinct from LLMServiceError (a model provider failed) and from a bare
    `HTTPException(503)`, which several call sites were raising directly and
    which bypasses this hierarchy entirely.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def _body(message: str, **extra) -> dict:
    """Every error body has the same shape: `detail` is always a human-readable
    string, plus the request id so a user can quote something findable."""
    return {"detail": message, "request_id": get_request_id(), **extra}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_body(exc.message))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalise FastAPI's 422 to the same shape as everything else.

    Pydantic returns `detail` as a *list of objects* while `UnprocessableError`
    returns a string — the same status code carrying two incompatible shapes,
    which no client can type. The per-field detail is still there, just under a
    key of its own.
    """
    errors = []
    for error in exc.errors():
        # Drop the leading "body"/"query" locator; the field name is what helps.
        location = [str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")]
        errors.append({"field": ".".join(location) or None, "message": error.get("msg", "Invalid value")})

    summary = "; ".join(
        f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_body(summary or "Request validation failed", errors=errors),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort. Logs the traceback against the request id and returns a body
    carrying that same id, so a user report can be tied to a specific failure
    instead of being an unfindable "it broke"."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_body("Something went wrong on our end. Please try again."),
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
