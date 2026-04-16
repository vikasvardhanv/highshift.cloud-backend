from temporalio import activity

from app.services.postgres_scheduler_service import publish_scheduled_post_by_id


@activity.defn
async def publish_scheduled_post_activity(post_id: str):
    return await publish_scheduled_post_by_id(post_id)

