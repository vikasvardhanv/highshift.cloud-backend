from datetime import datetime
from typing import List, Optional
from beanie import Document, Link
from pydantic import Field
from .user import User

class AnalyticsSnapshot(Document):
    user_id: Link[User] = Field(alias="userId")
    account_id: str = Field(alias="accountId")
    platform: str
    
    # metrics
    followers: int = 0
    impressions: int = 0
    engagement: int = 0
    
    # Optional detailed breakdown
    raw_data: Optional[dict] = Field(None, alias="rawData")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "analytics_snapshots"
        indexes = ["userId", "accountId", "timestamp"]
