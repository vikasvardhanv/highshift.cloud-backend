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
    print(f"DEBUG: Fetching schedule for user {user.id}")
    # Fix: User ID is stored as DBRef, so we query userId.$id. 
    # Also use alias 'scheduledFor' for sorting.
    posts = await ScheduledPost.find({"userId.$id": user.id}).sort("-scheduledFor").to_list()
    print(f"DEBUG: Found {len(posts)} posts for list view")
    return {"posts": posts}

@router.post("")
async def create_schedule(
    payload: dict = Body(...),
    user: User = Depends(get_current_user)
):
    # print(f"DEBUG: Create Schedule Payload: {payload}")
    content = payload.get("content")
    accounts = payload.get("accounts", []) # List of {platform, accountId}
    scheduled_time_str = payload.get("scheduledFor") # ISO string
    media_urls = payload.get("media", [])  # List of URLs (images/videos)
    
    if not content and not media_urls:
         print("DEBUG: Missing content/media")
         raise HTTPException(status_code=400, detail="Content or Media is required")
         
    if not accounts or not scheduled_time_str:
        print("DEBUG: Missing accounts or time")
        raise HTTPException(status_code=400, detail="Missing accounts or scheduled time")

    try:
        # Handle potential Z suffix or offset
        dt = datetime.datetime.fromisoformat(scheduled_time_str.replace("Z", "+00:00"))
        print(f"DEBUG: Parsed datetime: {dt}")
    except ValueError as e:
        print(f"DEBUG: Date parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    from app.models.scheduled_post import AccountTarget
    
    # Store user_id. Beanie handles Link creation automatically if we pass the ID or object?
    # Ensure user.id is valid.
    post = ScheduledPost(
        user_id=user, # Pass the User object directly to create the Link correctly
        content=content or "",
        accounts=[AccountTarget(**acc) for acc in accounts],
        scheduled_for=dt,
        media=media_urls,
        status="pending"
    )
    await post.insert()
    print(f"DEBUG: Scheduled Post Created with ID: {post.id} for User {user.id}")
    
    return {"success": True, "post": post}

@router.delete("/{post_id}")
async def delete_scheduled_post(
    post_id: str,
    user: User = Depends(get_current_user)
):
    from bson import ObjectId
    try:
        p_id = ObjectId(post_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    # Fix find_one query as well
    post = await ScheduledPost.find_one({"_id": p_id, "userId.$id": user.id})
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
    print(f"DEBUG: Fetching calendar for user {user.id}")
    # Fix Query and Sort
    posts = await ScheduledPost.find({"userId.$id": user.id}).sort("scheduledFor").to_list()
    print(f"DEBUG: Found {len(posts)} posts for calendar")
    
    # Group by date (YYYY-MM-DD)
    calendar_data = defaultdict(list)
    for post in posts:
        try:
            date_key = post.scheduled_for.strftime("%Y-%m-%d")
            calendar_data[date_key].append({
                "id": str(post.id),
                "content": post.content[:50] + "..." if len(post.content) > 50 else post.content,
                "time": post.scheduled_for.strftime("%H:%M"),
                "platforms": [acc.platform for acc in post.accounts] if post.accounts else [],
                "status": post.status
            })
        except Exception as e:
            print(f"DEBUG: Error processing post {post.id} for calendar: {e}")
    
    return {"calendar": dict(calendar_data)}

