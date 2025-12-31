from datetime import datetime
from typing import List, Optional
from beanie import Document
from pydantic import BaseModel, Field

class LinkedAccount(BaseModel):
    platform: str
    account_id: str = Field(alias="accountId")
    username: Optional[str] = None
    display_name: Optional[str] = Field(None, alias="displayName")
    access_token_enc: str = Field(alias="accessTokenEnc")
    refresh_token_enc: Optional[str] = Field(None, alias="refreshTokenEnc")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")
    scope: Optional[str] = None
    token_type: Optional[str] = Field(None, alias="tokenType")
    raw_profile: Optional[dict] = Field(None, alias="rawProfile")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "linked_accounts"

class User(Document):
    api_key_hash: str = Field(unique=True, alias="apiKeyHash")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    linked_accounts: List[LinkedAccount] = Field(default=[], alias="linkedAccounts")

    class Settings:
        name = "users"
        indexes = [
            "apiKeyHash",
            [("linkedAccounts.platform", 1), ("linkedAccounts.accountId", 1)]
        ]
