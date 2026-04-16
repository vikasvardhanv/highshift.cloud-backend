from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import AuthUser
from app.utils.auth import get_current_user
from app.db.postgres import create_scheduled_post, list_scheduled_posts, cancel_scheduled_post, insert_activity
from typing import List, Optional
import datetime
from collections import defaultdict

router = APIRouter(prefix="/schedule", tags=["Schedule"])

@router.get("")
async def get_schedule(
    user: AuthUser = Depends(get_current_user)
):
    posts = await list_scheduled_posts(str(user.id))
    return {
        "posts": [
            {
                "id": str(post["id"]),
                "content": post.get("content", ""),
                "media": post.get("media") or [],
                "status": post.get("status"),
                "scheduledFor": post["scheduled_for"].isoformat(),
                "scheduled_for": post["scheduled_for"].isoformat(),
                "accounts": [
                    {"platform": a.get("platform"), "accountId": a.get("accountId")}
                    for a in (post.get("accounts") or [])
                ],
                "target_accounts": [
                    {"platform": a.get("platform"), "accountId": a.get("accountId")}
                    for a in (post.get("accounts") or [])
                ],
                "error": post.get("error"),
            }
            for post in posts
        ]
    }

@router.post("")
async def create_schedule(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
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

    post = await create_scheduled_post(
        user_id=str(user.id),
        content=content or "",
        accounts=accounts,
        scheduled_for_iso=dt.isoformat(),
        media=media_urls,
    )

    # Log activity
    await insert_activity(
        user_id=str(user.id),
        title=f"Scheduled a post for {dt.strftime('%Y-%m-%d %H:%M')}",
        type_="success",
        platform="System",
        meta={"postId": str(post["id"])},
    )
    
    return {
        "success": True,
        "post": {
            "id": str(post["id"]),
            "content": post.get("content", ""),
            "status": post.get("status"),
            "scheduledFor": post["scheduled_for"].isoformat(),
            "media": post.get("media") or [],
            "accounts": accounts,
        },
    }

@router.delete("/{post_id}")
async def delete_scheduled_post(
    post_id: str,
    user: AuthUser = Depends(get_current_user)
):
    try:
        ok = await cancel_scheduled_post(str(user.id), post_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"success": True}


# ============ NEW: Calendar View Endpoint ============
@router.get("/calendar")
async def get_schedule_calendar(
    user: AuthUser = Depends(get_current_user)
):
    """
    Returns scheduled posts grouped by date for calendar display.
    """
    posts = await list_scheduled_posts(str(user.id))
    
    # Return flat list, let frontend handle grouping by local timezone
    calendar_events = []
    for post in posts:
        try:
           calendar_events.append({
                "id": str(post["id"]),
                "content": (
                    post.get("content", "")[:50] + "..."
                    if len(post.get("content", "")) > 50
                    else post.get("content", "")
                ),
                "time": post["scheduled_for"].isoformat(),
                "platforms": [
                    acc.get("platform") for acc in (post.get("accounts") or [])
                ],
                "status": post.get("status"),
                "media": post.get("media") or [],
            })
        except Exception:
            continue
    
    return {"calendar": calendar_events} # Changed from dict to list wrapper
