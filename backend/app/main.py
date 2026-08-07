import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.core.request_context import RequestIdFilter, RequestIdMiddleware
from app.db.session import AsyncSessionLocal
from app.services.match_reaper import sweep_stale_matches
from app.services.storage_service import ensure_bucket

settings = get_settings()

# Without this, nothing the application logs below WARNING is ever emitted:
# uvicorn configures handlers for its own loggers only, and the root logger falls
# back to a WARNING-level handler of last resort. Every `logger.info(...)` in
# services/ was being written to nowhere — which was discovered the hard way,
# while trying to diagnose a live failure using logging that didn't exist.
logging.basicConfig(
    level=settings.log_level.upper(),
    # request_id ties every line to the response the user saw. Supplied by
    # RequestIdFilter, which defaults it to "-" outside a request.
    format="%(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
    # uvicorn --reload re-imports this module; without force the second pass is a
    # no-op (basicConfig does nothing once the root logger has a handler) and the
    # level silently stays wherever it was.
    force=True,
)
for _handler in logging.getLogger().handlers:
    _handler.addFilter(RequestIdFilter())

logger = logging.getLogger(__name__)


async def _reaper_loop() -> None:
    """Periodically fail matches that will never finish. See match_reaper.py.

    Runs in every API replica. That is harmless — the sweep is an idempotent
    conditional UPDATE — and it means the behaviour doesn't depend on exactly one
    process being designated for it.
    """
    interval = settings.stale_match_sweep_interval_seconds
    stale_after = timedelta(seconds=settings.stale_match_after_seconds)
    while True:
        try:
            await asyncio.sleep(interval)
            async with AsyncSessionLocal() as db:
                await sweep_stale_matches(db, stale_after)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A sweep failing must never take the API down with it.
            logger.exception("Stale-match sweep failed; will retry next interval")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    reaper = asyncio.create_task(_reaper_loop())
    try:
        yield
    finally:
        reaper.cancel()
        # Let the task observe the cancellation so shutdown isn't noisy.
        await asyncio.gather(reaper, return_exceptions=True)


app = FastAPI(title="Jaagir Sathi API", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
# Outermost, so the id is set before anything else can log or fail.
app.add_middleware(RequestIdMiddleware)


async def rate_limit_handler(request, exc: RateLimitExceeded):
    # Retry-After lets a client back off intelligently instead of hammering the
    # endpoint until something works. slowapi knows the window; surface it.
    retry_after = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down and try again shortly."},
        headers={"Retry-After": str(int(retry_after))},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

register_exception_handlers(app)

# Auth is Bearer-token based (no cookies), so allow_credentials stays False.
# The origin list is explicit rather than "*": the frontend now exists and has a
# known origin, which is what the original permissive setting was waiting for.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)


@app.get("/health")
async def health():
    """Liveness only — is this process up and serving?

    Deliberately does not touch Postgres, Redis or S3. See /health/ready for
    that: a liveness probe that fails when a dependency blips gets the container
    restarted, which fixes nothing and loses in-flight requests.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    """Readiness — can this process actually do its job right now?

    The old single `/health` returned a static literal, so it stayed green while
    the database was down and told an operator nothing.
    """
    checks: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.warning("Readiness: database check failed", exc_info=True)
        checks["database"] = "error"

    try:
        from app.workers.queue import get_redis_connection

        await asyncio.to_thread(get_redis_connection().ping)
        checks["redis"] = "ok"
    except Exception:
        logger.warning("Readiness: redis check failed", exc_info=True)
        checks["redis"] = "error"

    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "checks": checks},
    )
