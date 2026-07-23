from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.auth import router as auth_router
from app.api.v1.interviews import router as interviews_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.matches import router as matches_router
from app.api.v1.resumes import router as resumes_router
from app.api.v1.usage import router as usage_router
from app.models.user import User
from app.schemas.auth import UserResponse

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(resumes_router)
api_router.include_router(jobs_router)
api_router.include_router(matches_router)
api_router.include_router(interviews_router)
api_router.include_router(usage_router)


@api_router.get("/auth/me", response_model=UserResponse, tags=["auth"])
async def me(current_user: User = Depends(get_current_user)):
    return current_user
