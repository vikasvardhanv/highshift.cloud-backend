"""
Cron Routes - Endpoints triggered by Vercel Cron Jobs
"""
import os
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/cron", tags=["Cron"])

def verify_cron_secret(request: Request):
    """Verify the request is from Vercel Cron or has valid secret."""
    # Vercel Cron Jobs include this header
    vercel_cron_header = request.headers.get("x-vercel-cron")
    if vercel_cron_header:
        return True
    
    # Fallback: check for manual secret
    auth_header = request.headers.get("authorization")
    cron_secret = os.getenv("CRON_SECRET", "")
    if cron_secret and auth_header == f"Bearer {cron_secret}":
        return True
    
    return False

@router.post("/publish-scheduled")
@router.get("/publish-scheduled")  # GET also works for Vercel Cron
async def publish_scheduled_posts(request: Request):
    """
    Process and publish any due scheduled posts.
    Called by Vercel Cron every minute.
    """
    # Verify this is a legitimate cron request
    if not verify_cron_secret(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Ensure DB is initialized
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

    # Process due posts from Postgres scheduler queue.
    from app.services.postgres_scheduler_service import process_due_posts
    stats = await process_due_posts(limit=100)

    return {
        "status": "ok",
        "message": "Scheduled posts check completed",
        "stats": stats,
    }
