from fastapi import APIRouter, Depends, Query
from app.models.user import User
from app.models.activity import ActivityLog
from app.utils.auth import get_current_user
from typing import List

async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/activity", tags=["Activity"], dependencies=[Depends(ensure_db)])

@router.get("/recent")
async def get_recent_activity(
    limit: int = 20,
    user: User = Depends(get_current_user)
):
    """
    Fetch recent activity logs for the user.
    """
    logs = await ActivityLog.find(
        ActivityLog.user_id.id == user.id
    ).sort("-time").limit(limit).to_list()
    
    return {"activity": logs}
