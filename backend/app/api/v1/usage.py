from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import UsageResponse
from app.services.usage_service import usage_snapshot

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
async def get_usage(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await usage_snapshot(db, current_user)
