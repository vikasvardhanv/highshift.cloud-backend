from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from pymongo import ReturnDocument

from app.models.scheduled_post import AccountTarget, ScheduledPost
from app.models.user import User


class PostWorkflowService:
    """
    Postiz-inspired workflow/state manager for scheduled posts.
    Keeps state transitions explicit and centralizes scheduling operations.
    """

    TERMINAL_STATES = {"published", "failed", "canceled"}
    ACTIVE_STATES = {"pending", "processing"}

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def create_scheduled_post(
        self,
        user: User,
        content: str,
        accounts: List[Dict[str, str]],
        scheduled_for: datetime,
        media: Optional[List[str]] = None,
    ) -> ScheduledPost:
        normalized_accounts = [
            AccountTarget(
                platform=a.get("platform", "").strip().lower(),
                accountId=a.get("accountId") or a.get("account_id"),
            )
            for a in accounts
        ]

        post = ScheduledPost(
            userId=PydanticObjectId(str(user.id)),
            content=content,
            accounts=normalized_accounts,
            scheduledFor=self._as_utc(scheduled_for),
            media=media or [],
            status="pending",
            attempts=0,
        )
        await post.insert()
        return post

    async def claim_next_due_post(self) -> Optional[ScheduledPost]:
        """
        Atomically claims one due post.
        Prevents duplicate processing when multiple scheduler loops exist.
        """
        collection = ScheduledPost.get_pymongo_collection()
        now = self._utc_now()
        raw = await collection.find_one_and_update(
            {
                "status": "pending",
                "scheduledFor": {"$lte": now},
            },
            {
                "$set": {
                    "status": "processing",
                    "lastAttemptAt": now,
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("scheduledFor", 1)],
            return_document=ReturnDocument.AFTER,
        )

        if not raw:
            return None

        return await ScheduledPost.get(raw["_id"])

    async def mark_published(self, post_id: PydanticObjectId, result: Any) -> None:
        collection = ScheduledPost.get_pymongo_collection()
        now = self._utc_now()
        await collection.update_one(
            {"_id": post_id},
            {
                "$set": {
                    "status": "published",
                    "result": result,
                    "error": None,
                    "publishedAt": now,
                    "updated_at": now,
                }
            },
        )

    async def mark_failed(self, post_id: PydanticObjectId, error: str) -> None:
        collection = ScheduledPost.get_pymongo_collection()
        now = self._utc_now()
        await collection.update_one(
            {"_id": post_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error[:2000] if error else "Unknown error",
                    "updated_at": now,
                }
            },
        )

    async def cancel_post_for_user(
        self, post_id: str, user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Cancels a post only if it belongs to the user and is still active.
        """
        collection = ScheduledPost.get_pymongo_collection()
        now = self._utc_now()
        raw = await collection.find_one_and_update(
            {
                "_id": PydanticObjectId(post_id),
                "$or": [
                    {"userId.$id": PydanticObjectId(user_id)},
                    {"userId._id": PydanticObjectId(user_id)},
                    {"userId": PydanticObjectId(user_id)},
                ],
                "status": {"$in": list(self.ACTIVE_STATES)},
            },
            {"$set": {"status": "canceled", "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not raw:
            return False, None
        return True, str(raw.get("_id"))


post_workflow_service = PostWorkflowService()
