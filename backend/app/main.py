import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.services.storage_service import ensure_bucket

# Without this, nothing the application logs below WARNING is ever emitted:
# uvicorn configures handlers for its own loggers only, and the root logger falls
# back to a WARNING-level handler of last resort. Every `logger.info(...)` in
# services/ was being written to nowhere — which was discovered the hard way,
# while trying to diagnose a live failure using logging that didn't exist.
logging.basicConfig(
    level=get_settings().log_level.upper(),
    format="%(levelname)-8s %(name)s: %(message)s",
    # uvicorn --reload re-imports this module; without force the second pass is a
    # no-op (basicConfig does nothing once the root logger has a handler) and the
    # level silently stays wherever it was.
    force=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="Jaagir Sathi API", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


async def rate_limit_handler(request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

register_exception_handlers(app)

# No frontend origin exists yet — permissive CORS for now, tighten once the
# frontend phase defines NEXT_PUBLIC_APP_URL. Auth is Bearer-token based (no
# cookies), so allow_credentials stays False — that's what permits a wildcard origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
