"""Correlation ids.

An unhandled exception produced a bare 500 with nothing tying it to a log line,
so "the report page broke for me a minute ago" was unactionable — there was no
way to find the traceback that belonged to it. Every response now carries an id,
every log record emitted while handling that request carries the same id, and
error bodies repeat it so a user can quote it.
"""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"

# "-" rather than None so the log format never renders "None" for work that
# happens outside a request (startup, the reaper loop, RQ jobs).
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adopt an inbound request id or mint one, and echo it back.

    Accepting a client-supplied value lets a trace span the frontend and the API;
    it is only ever used for correlation, never for auth or lookup, so an
    attacker-chosen value is harmless. Length-capped so it can't bloat every log
    line in the process.
    """

    def __init__(self, app: ASGIApp, max_length: int = 64):
        super().__init__(app)
        self.max_length = max_length

    async def dispatch(self, request, call_next):
        incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
        request_id = incoming[: self.max_length] if incoming else uuid.uuid4().hex[:16]

        token = _request_id.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RequestIdFilter(logging.Filter):
    """Makes `%(request_id)s` available to every formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
