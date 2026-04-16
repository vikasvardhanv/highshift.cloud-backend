from fastapi import APIRouter, Depends, Query, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import list_activity

router = APIRouter(prefix="/activity", tags=["Activity"])

@router.get("/recent")
async def get_recent_activity(
    limit: int = 20,
    user: AuthUser = Depends(get_current_user)
):
    logs = await list_activity(str(user.id), limit=limit)
    return {"activity": logs}
