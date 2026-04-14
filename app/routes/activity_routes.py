from fastapi import APIRouter, Depends, Query, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import list_activity
from typing import List

async def ensure_db():
    from main import ensure_beanie_initialized
    ok = await ensure_beanie_initialized()
    if not ok:
        raise HTTPException(status_code=503, detail="Database unavailable")

router = APIRouter(prefix="/activity", tags=["Activity"], dependencies=[Depends(ensure_db)])

@router.get("/recent")
async def get_recent_activity(
    limit: int = 20,
    user: AuthUser = Depends(get_current_user)
):
    """
    Fetch recent activity logs for the user.
    """
    logs = await list_activity(str(user.id), limit=limit)
    return {"activity": logs}
