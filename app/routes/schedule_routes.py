from fastapi import APIRouter, Depends, HTTPException, Body
from app.models.user import User
from app.models.scheduled_post import ScheduledPost
from app.utils.auth import get_current_user
from typing import List, Optional
import datetime
from collections import defaultdict

async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/schedule", tags=["Schedule"], dependencies=[Depends(ensure_db)])

@router.get("")
async def get_schedule(
    user: User = Depends(get_current_user)
):
    posts = await ScheduledPost.find(ScheduledPost.user_id == user.id).sort("-scheduled_time").to_list()
    return {"posts": posts}

@router.post("")
async def create_schedule(
    payload: dict = Body(...),
    user: User = Depends(get_current_user)
):
    content = payload.get("content")
    accounts = payload.get("accounts", []) # List of {platform, accountId}
    scheduled_time_str = payload.get("scheduledFor") # ISO string
    media_urls = payload.get("media", [])  # Optional media URLs
    
    if not content or not accounts or not scheduled_time_str:
        raise HTTPException(status_code=400, detail="Missing required fields")

    try:
        dt = datetime.datetime.fromisoformat(scheduled_time_str.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    # In a real app, 'target_accounts' would check if these accounts actually belong to the user
    # For now we assume they are valid if the user passed them (MVP)
    
    post = ScheduledPost(
        user_id=user.id,
        content=content,
        target_accounts=accounts, # Assuming schema matches or we adapt it
        scheduled_time=dt,
        media_urls=media_urls,
        status="scheduled"
    )
    await post.insert()
    
    return {"success": True, "post": post}

@router.delete("/{post_id}")
async def delete_scheduled_post(
    post_id: str,
    user: User = Depends(get_current_user)
):
    # In Beanie we need Pydantic ObjectId usually, but find_one works with string if defined carefully
    # Assuming str works or converting if needed. Beanie handles str -> ObjectId often automatically.
    from bson import ObjectId
    try:
        p_id = ObjectId(post_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    post = await ScheduledPost.find_one(ScheduledPost.id == p_id, ScheduledPost.user_id == user.id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    await post.delete()
    return {"success": True}


# ============ NEW: Calendar View Endpoint ============
@router.get("/calendar")
async def get_schedule_calendar(
    user: User = Depends(get_current_user)
):
    """
    Returns scheduled posts grouped by date for calendar display.
    """
    posts = await ScheduledPost.find(ScheduledPost.user_id == user.id).sort("scheduled_time").to_list()
    
    # Group by date (YYYY-MM-DD)
    calendar_data = defaultdict(list)
    for post in posts:
        date_key = post.scheduled_time.strftime("%Y-%m-%d")
        calendar_data[date_key].append({
            "id": str(post.id),
            "content": post.content[:50] + "..." if len(post.content) > 50 else post.content,
            "time": post.scheduled_time.strftime("%H:%M"),
            "platforms": [acc.get("platform") for acc in post.target_accounts] if post.target_accounts else [],
            "status": post.status
        })
    
    return {"calendar": dict(calendar_data)}

