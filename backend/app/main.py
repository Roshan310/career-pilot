from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.services.storage_service import ensure_bucket


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
