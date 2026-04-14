from fastapi import APIRouter, Depends, Query, HTTPException
from app.models.user import User
from app.models.activity import ActivityLog
from app.utils.auth import get_current_user
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
    user: User = Depends(get_current_user)
):
    """
    Fetch recent activity logs for the user.
    """
    from bson import ObjectId
    uid = ObjectId(user.id)
    logs = await ActivityLog.find(
        {"$or": [{"userId.$id": uid}, {"userId._id": uid}, {"userId": uid}]}
    ).sort("-time").limit(limit).to_list()
    
    return {"activity": logs}
