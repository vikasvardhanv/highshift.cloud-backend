from datetime import datetime
from typing import Optional
from beanie import Document, Link
from pydantic import Field
from .user import User

class ActivityLog(Document):
    user_id: Link[User] = Field(alias="userId")
    title: str
    platform: Optional[str] = None
    time: datetime = Field(default_factory=datetime.utcnow)
    type: str = Field(default="info") # info, success, error, warning
    meta: Optional[dict] = None # For extra data like post_id

    class Settings:
        name = "activity_logs"
        indexes = ["userId", "time"]
