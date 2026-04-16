from datetime import datetime, timedelta, timezone

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import publish_scheduled_post_activity


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

