from datetime import datetime
from typing import List, Optional, Any
from beanie import Document, Link
from pydantic import Field, BaseModel
from .user import User

class AccountTarget(BaseModel):
    platform: str
    account_id: str = Field(alias="accountId")

class ScheduledPost(Document):
    user_id: Link[User] = Field(alias="userId")
    accounts: List[AccountTarget]
    content: str = Field(max_length=2800)
    media: List[str] = Field(default=[])
    scheduled_for: datetime = Field(alias="scheduledFor")
    status: str = Field(default="pending") # pending, processing, published, failed, canceled
    job_id: Optional[str] = Field(None, alias="jobId")
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "scheduled_posts"
        indexes = ["userId", "scheduledFor", "status"]
