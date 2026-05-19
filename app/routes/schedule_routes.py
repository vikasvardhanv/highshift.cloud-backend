from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import AuthUser
from app.utils.auth import get_current_user
from app.db.postgres import create_scheduled_post, list_scheduled_posts, cancel_scheduled_post
import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["Schedule"])


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def _process_due_posts_safely(limit: int = 10):
    try:
        from app.services.postgres_scheduler_service import process_due_posts
        stats = await process_due_posts(limit=limit)
        if stats.get("processed"):
            logger.info("Processed due scheduled posts from schedule route: %s", stats)
        return stats
    except Exception as e:
        logger.error("Failed to process due scheduled posts from schedule route: %s", e, exc_info=True)
        return {"processed": 0, "published": 0, "failed": 0, "error": str(e)}


@router.get("")
async def get_schedule(
    user: AuthUser = Depends(get_current_user)
):
    await _process_due_posts_safely(limit=10)
    posts = await list_scheduled_posts(str(user.id))
    return {
        "posts": [
            {
                "id": str(post["id"]),
                "content": post.get("content", ""),
                "media": post.get("media") or [],
                "status": post.get("status"),
                "scheduledFor": _iso(post["scheduled_for"]),
                "scheduled_for": _iso(post["scheduled_for"]),
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

    try:
        post = await create_scheduled_post(
            user_id=str(user.id),
            content=content or "",
            accounts=accounts,
            scheduled_for_iso=dt.isoformat(),
            media=media_urls,
        )
    except Exception as e:
        logger.error(
            "Failed to create scheduled post: user_id=%s account_count=%s scheduled_for=%s media_count=%s error=%s",
            str(user.id),
            len(accounts or []),
            dt.isoformat(),
            len(media_urls or []),
            e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to schedule post")

    return {
        "success": True,
        "post": {
            "id": str(post["id"]),
            "content": post.get("content", ""),
            "status": post.get("status"),
            "scheduledFor": _iso(post["scheduled_for"]),
            "media": post.get("media") or [],
            "accounts": accounts,
            "jobId": post.get("job_id"),
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


@router.post("/process-due")
@router.get("/process-due")
async def process_due_scheduled_posts(
    user: AuthUser = Depends(get_current_user)
):
    stats = await _process_due_posts_safely(limit=25)
    return {"success": True, "stats": stats}


# ============ NEW: Calendar View Endpoint ============
@router.get("/calendar")
async def get_schedule_calendar(
    user: AuthUser = Depends(get_current_user)
):
    """
    Returns scheduled posts grouped by date for calendar display.
    """
    await _process_due_posts_safely(limit=10)
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
                "scheduledFor": _iso(post["scheduled_for"]),
                "scheduled_for": _iso(post["scheduled_for"]),
                "time": _iso(post["scheduled_for"]),
                "platforms": [
                    acc.get("platform") for acc in (post.get("accounts") or [])
                ],
                "status": post.get("status"),
                "media": post.get("media") or [],
                "error": post.get("error"),
            })
        except Exception:
            continue
    
    return {"calendar": calendar_events} # Changed from dict to list wrapper
