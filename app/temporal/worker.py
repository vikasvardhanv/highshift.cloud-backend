from temporalio.worker import Worker

from app.temporal.activities import publish_scheduled_post_activity
from app.temporal.client import get_temporal_client, get_temporal_task_queue
from app.temporal.workflows import ScheduledPostWorkflow


async def run_temporal_worker():
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=get_temporal_task_queue(),
        workflows=[ScheduledPostWorkflow],
        activities=[publish_scheduled_post_activity],
    )
    await worker.run()

