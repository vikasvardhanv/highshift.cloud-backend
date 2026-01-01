from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.models.scheduled_post import ScheduledPost
from app.utils.auth import get_current_user
from typing import List

async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/posts", tags=["History"], dependencies=[Depends(ensure_db)])

@router.get("/history")
async def get_post_history(
    user: User = Depends(get_current_user)
):
    # Find all posts (scheduled, published, failed)
    # Ideally separate collection for 'History' logs or query ScheduledPost with status != scheduled
    # For MVP we re-use ScheduledPost table as the single source of truth for posts
    
    # We might assume 'published' or 'failed' stay in ScheduledPost
    posts = await ScheduledPost.find(ScheduledPost.user_id == user.id).sort("-created_at").to_list()
    return {"posts": posts}
