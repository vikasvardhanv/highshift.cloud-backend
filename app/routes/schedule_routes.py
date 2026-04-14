from fastapi import APIRouter, Depends, HTTPException, Body
from app.models.user import User
from app.models.scheduled_post import ScheduledPost
from app.utils.auth import get_current_user
from app.services.workflow_service import post_workflow_service
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
    from bson import ObjectId
    uid = ObjectId(user.id)
    posts = await ScheduledPost.find(
        {"$or": [{"userId.$id": uid}, {"userId._id": uid}, {"userId": uid}]}
    ).sort("-scheduled_for").to_list()
    return {
        "posts": [
            {
                "id": str(post.id),
                "content": post.content,
                "media": post.media,
                "status": post.status,
                "scheduledFor": post.scheduled_for.isoformat(),
                "scheduled_for": post.scheduled_for.isoformat(),
                "accounts": [
                    {"platform": a.platform, "accountId": a.account_id}
                    for a in post.accounts
                ],
                "target_accounts": [
                    {"platform": a.platform, "accountId": a.account_id}
                    for a in post.accounts
                ],
                "error": post.error,
            }
            for post in posts
        ]
    }

@router.post("")
async def create_schedule(
    payload: dict = Body(...),
    user: User = Depends(get_current_user)
):
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
        dt = datetime.datetime.fromisoformat(str(scheduled_time_str).replace("Z", "+00:00"))
        # Ensure it is timezone aware, if naive assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    if dt <= datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    post = await post_workflow_service.create_scheduled_post(
        user=user,
        content=content or "",
        accounts=accounts,
        scheduled_for=dt,
        media=media_urls,
    )

    # Log activity
    from app.models.activity import ActivityLog
    await ActivityLog(
        userId=user,
        title=f"Scheduled a post for {post.scheduled_for.strftime('%Y-%m-%d %H:%M')}",
        type="success",
        platform="System",
        meta={"postId": str(post.id)}
    ).insert()
    
    return {
        "success": True,
        "post": {
            "id": str(post.id),
            "content": post.content,
            "status": post.status,
            "scheduledFor": post.scheduled_for.isoformat(),
            "media": post.media,
            "accounts": [
                {"platform": a.platform, "accountId": a.account_id} for a in post.accounts
            ],
        },
    }

@router.delete("/{post_id}")
async def delete_scheduled_post(
    post_id: str,
    user: User = Depends(get_current_user)
):
    try:
        ok, _ = await post_workflow_service.cancel_post_for_user(post_id, str(user.id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True}


# ============ NEW: Calendar View Endpoint ============
@router.get("/calendar")
async def get_schedule_calendar(
    user: User = Depends(get_current_user)
):
    """
    Returns scheduled posts grouped by date for calendar display.
    """
    from bson import ObjectId
    uid = ObjectId(user.id)
    posts = await ScheduledPost.find(
        {"$or": [{"userId.$id": uid}, {"userId._id": uid}, {"userId": uid}]}
    ).sort("scheduled_for").to_list()
    
    # Return flat list, let frontend handle grouping by local timezone
    calendar_events = []
    for post in posts:
        try:
           calendar_events.append({
                "id": str(post.id),
                "content": post.content[:50] + "..." if len(post.content) > 50 else post.content,
                "time": post.scheduled_for.isoformat(), # Return full ISO (UTC)
                "platforms": [acc.platform for acc in post.accounts] if post.accounts else [],
                "status": post.status,
                "media": post.media # Include media to debug empty media issues
            })
        except Exception:
            continue
    
    return {"calendar": calendar_events} # Changed from dict to list wrapper
