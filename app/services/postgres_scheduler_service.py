import logging
from typing import Any, Dict, Optional

from app.db.postgres import (
    claim_next_due_scheduled_post,
    claim_scheduled_post_by_id,
    fetch_user_by_id,
    insert_activity,
    mark_scheduled_post_failed,
    mark_scheduled_post_published,
)
from app.services.publishing_service import publish_content
from app.utils.auth import _to_auth_user

logger = logging.getLogger("postgres_scheduler")


async def _publish_claimed_post(post: Dict[str, Any]) -> Dict[str, Any]:
    user_row = await fetch_user_by_id(str(post["user_id"]))
    if not user_row:
        await mark_scheduled_post_failed(str(post["id"]), "User not found")
        return {"status": "failed", "error": "User not found"}

    user = _to_auth_user(user_row)
    accounts = post.get("accounts") or []

    try:
        result = await publish_content(
            user=user,
            content=post.get("content") or "",
            accounts=accounts,
            media_urls=post.get("media") or [],
            local_media_paths=[],
        )
        await mark_scheduled_post_published(str(post["id"]), result)
        await insert_activity(
            user_id=str(user.id),
            title=f"Scheduled post published ({len(accounts)} platforms)",
            type_="success",
            platform="System",
            meta={"postId": str(post["id"])},
        )
        return {"status": "published", "result": result}
    except Exception as e:
        logger.error("Scheduled post %s failed: %s", post["id"], e, exc_info=True)
        await mark_scheduled_post_failed(str(post["id"]), str(e))
        return {"status": "failed", "error": str(e)}


async def publish_scheduled_post_by_id(post_id: str) -> Dict[str, Any]:
    """
    Claims and publishes one specific post if it's currently due.
    """
    post = await claim_scheduled_post_by_id(post_id)
    if not post:
        return {"status": "skipped", "reason": "not_due_or_not_pending"}
    return await _publish_claimed_post(post)


async def process_due_posts(limit: int = 50) -> Dict[str, int]:
    """
    Claims and processes due posts in FIFO order.
    """
    processed = 0
    published = 0
    failed = 0

    while processed < limit:
        post = await claim_next_due_scheduled_post()
        if not post:
            break
        processed += 1
        result = await _publish_claimed_post(post)
        if result["status"] == "published":
            published += 1
        else:
            failed += 1

    return {"processed": processed, "published": published, "failed": failed}

