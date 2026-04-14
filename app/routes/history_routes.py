from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_current_user, AuthUser
from app.db.postgres import list_scheduled_posts
from typing import List

async def ensure_db():
    from main import ensure_beanie_initialized
    ok = await ensure_beanie_initialized()
    if not ok:
        raise HTTPException(status_code=503, detail="Database unavailable")

router = APIRouter(prefix="/posts", tags=["History"], dependencies=[Depends(ensure_db)])

@router.get("/history")
async def get_post_history(
    user: AuthUser = Depends(get_current_user)
):
    # Find all posts (scheduled, published, failed)
    # Ideally separate collection for 'History' logs or query ScheduledPost with status != scheduled
    # For MVP we re-use ScheduledPost table as the single source of truth for posts
    
    # We might assume 'published' or 'failed' stay in ScheduledPost
    posts = await list_scheduled_posts(str(user.id))
    return {"posts": posts}
