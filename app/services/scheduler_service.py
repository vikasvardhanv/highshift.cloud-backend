import asyncio
import logging
from datetime import datetime, timezone
from app.models.activity import ActivityLog
from app.services.publishing_service import publish_content
from app.services.workflow_service import post_workflow_service

logger = logging.getLogger("scheduler")

class BackgroundScheduler:
    def __init__(self):
        self.is_running = False
        self._task = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Background Scheduler started")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Background Scheduler stopped")

    async def _loop(self):
        while self.is_running:
            try:
                await self.check_due_posts()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
            
            # Wait for 60 seconds before next check
            await asyncio.sleep(60)

    async def check_due_posts(self):
        """
        Atomically claims due posts and publishes them.
        """
        processed = 0
        while True:
            post = await post_workflow_service.claim_next_due_post()
            if not post:
                break
            try:
                # Resolve link lazily and safely
                await post.fetch_link(post.__class__.user_id)
                user = post.user_id
                if not user:
                    await post_workflow_service.mark_failed(post.id, "User not found")
                    logger.error("User not found for scheduled post %s", post.id)
                    continue

                # Prepare accounts list for service
                accounts_list = [{"platform": acc.platform, "accountId": acc.account_id} for acc in post.accounts]
                
                # Call publishing service
                # Note: Scheduled posts store media as URLs usually
                result = await publish_content(
                    user=user,
                    content=post.content,
                    accounts=accounts_list,
                    media_urls=post.media,
                    local_media_paths=[] 
                )
                
                await post_workflow_service.mark_published(post.id, result)
                
                # Log general activity
                await ActivityLog(
                    userId=str(user.id),
                    title=f"Scheduled post published ({len(post.accounts)} platforms)",
                    type="success",
                    meta={"postId": str(post.id)}
                ).insert()
                processed += 1
                logger.info("Successfully processed scheduled post %s", post.id)

            except Exception as e:
                logger.error("Failed to process scheduled post %s: %s", post.id, e, exc_info=True)
                await post_workflow_service.mark_failed(post.id, str(e))

        if processed:
            logger.info("Scheduler cycle complete, processed=%s", processed)

scheduler = BackgroundScheduler()
