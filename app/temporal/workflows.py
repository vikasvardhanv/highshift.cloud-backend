from datetime import datetime, timedelta, timezone

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import publish_scheduled_post_activity, search_for_missed_posts_activity
    from app.temporal.scheduler import schedule_post_workflow


def _parse_iso_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@workflow.defn
class ScheduledPostWorkflow:
    @workflow.run
    async def run(self, post_id: str, scheduled_for_iso: str):
        scheduled_for = _parse_iso_utc(scheduled_for_iso)
        now = workflow.now()
        delay = (scheduled_for - now).total_seconds()
        if delay > 0:
            await workflow.sleep(delay)

        return await workflow.execute_activity(
            publish_scheduled_post_activity,
            post_id,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(minutes=1),
                backoff_coefficient=2.0,
                maximum_attempts=5,
            ),
        )


@workflow.defn
class MissingPostWorkflow:
    @workflow.run
    async def run(self):
        """
        Continuously search for missed posts (posts scheduled > 3 hours ago but still pending)
        and trigger their workflows.
        """
        while True:
            try:
                missed_posts = await workflow.execute_activity(
                    search_for_missed_posts_activity,
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=30),
                        maximum_attempts=3,
                        backoff_coefficient=1.5,
                    ),
                )

                for post in missed_posts:
                    post_id = post.get("id")
                    scheduled_for = post.get("scheduled_for") or post.get("scheduled_time")
                    if post_id and scheduled_for:
                        try:
                            await schedule_post_workflow(post_id, _parse_iso_utc(scheduled_for))
                        except Exception as e:
                            workflow.logger.warning(f"Failed to schedule missed post {post_id}: {e}")

            except Exception as e:
                workflow.logger.error(f"Error in missing post workflow: {e}")

            # Wait for 1 hour before next check
            await workflow.sleep(timedelta(hours=1))

