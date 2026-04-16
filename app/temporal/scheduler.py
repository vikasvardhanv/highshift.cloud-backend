import logging
from datetime import datetime, timezone
from typing import Optional

from temporalio.exceptions import WorkflowAlreadyStartedError

from app.db.postgres import set_scheduled_post_job_id
from app.temporal.client import (
    get_temporal_client,
    get_temporal_task_queue,
    is_temporal_enabled,
)
from app.temporal.workflows import ScheduledPostWorkflow

logger = logging.getLogger("temporal_scheduler")


def _to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


async def schedule_post_workflow(post_id: str, scheduled_for: datetime) -> Optional[str]:
    """
    Starts a Temporal workflow for one scheduled post if Temporal is enabled.
    """
    if not is_temporal_enabled():
        return None

    workflow_id = f"scheduled_post_{post_id}"
    client = await get_temporal_client()
    try:
        await client.start_workflow(
            ScheduledPostWorkflow.run,
            post_id,
            _to_iso_utc(scheduled_for),
            id=workflow_id,
            task_queue=get_temporal_task_queue(),
        )
    except WorkflowAlreadyStartedError:
        logger.info("Workflow already exists for post %s", post_id)

    await set_scheduled_post_job_id(post_id, workflow_id)
    return workflow_id
