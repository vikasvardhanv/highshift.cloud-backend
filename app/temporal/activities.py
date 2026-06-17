from temporalio import activity

from app.db.postgres import find_missed_scheduled_posts
from app.services.postgres_scheduler_service import publish_scheduled_post_by_id


@activity.defn
async def publish_scheduled_post_activity(post_id: str):
    return await publish_scheduled_post_by_id(post_id)


@activity.defn
async def search_for_missed_posts_activity():
    """Search for posts that were missed in the last 3 hours and return them."""
    missed_posts = await find_missed_scheduled_posts(hours_back=3)
    return missed_posts

