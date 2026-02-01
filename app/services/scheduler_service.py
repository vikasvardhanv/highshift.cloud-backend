import asyncio
import logging
from datetime import datetime, timezone
from app.models.scheduled_post import ScheduledPost
from app.models.user import User
from app.models.activity import ActivityLog
from app.services.publishing_service import publish_content

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
        Finds pending posts that are due and publishes them.
        """
        now = datetime.now(timezone.utc)
        # Find posts that are pending and scheduled time is passed
        due_posts = await ScheduledPost.find(
            ScheduledPost.status == "pending",
            ScheduledPost.scheduled_for <= now
        ).to_list()

        if not due_posts:
            return

        logger.info(f"Found {len(due_posts)} due posts to publish")

        for post in due_posts:
            # Lock the post effectively by setting status to processing
            post.status = "processing"
            await post.save()
            
            try:
                # Fetch user to get tokens
                user = await User.get(post.user_id.ref.id)
                if not user:
                    logger.error(f"User {post.user_id.ref.id} not found for scheduled post {post.id}")
                    post.status = "failed"
                    post.error = "User not found"
                    await post.save()
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
                
                # Check results
                # If at least one platform succeeded, we mark as published (or partial)
                # For now, simplistic: if logic ran, mark published, store detailed result
                post.result = result
                post.status = "published"
                await post.save()
                
                # Log general activity
                await ActivityLog(
                    userId=str(user.id),
                    title=f"Scheduled post published ({len(post.accounts)} platforms)",
                    type="success",
                    meta={"postId": str(post.id)}
                ).insert()
                
                logger.info(f"Successfully processed scheduled post {post.id}")

            except Exception as e:
                logger.error(f"Failed to process scheduled post {post.id}: {e}", exc_info=True)
                post.status = "failed"
                post.error = str(e)
                await post.save()

scheduler = BackgroundScheduler()
