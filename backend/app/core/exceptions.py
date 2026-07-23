from fastapi import Request, status
from fastapi.responses import JSONResponse


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


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
