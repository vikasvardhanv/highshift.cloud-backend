from datetime import datetime
import uuid
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
    profile_name: Optional[str] = Field(None, alias="profileName")  # NEW: Link to profile

    class Settings:
        name = "linked_accounts"

class ApiKey(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Default Key"
    key_hash: str = Field(alias="keyHash")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = Field(None, alias="lastUsed")

class Profile(BaseModel):
    """A named profile to group social accounts (e.g., 'business', 'personal')."""
    name: str  # Unique per user, case-sensitive
    created_at: datetime = Field(default_factory=datetime.utcnow)

class User(Document):
    api_key_hash: str = Field(unique=True, alias="apiKeyHash")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    api_keys: List[ApiKey] = Field(default=[], alias="apiKeys")
    linked_accounts: List[LinkedAccount] = Field(default=[], alias="linkedAccounts")
    profiles: List[Profile] = Field(default=[], alias="profiles")  # NEW
    
    # B2B / Limits
    plan_tier: str = Field(default="starter", alias="planTier")
    max_profiles: int = Field(default=5, alias="maxProfiles")

    # New Auth Fields
    email: Optional[str] = Field(None, unique=True)
    password_hash: Optional[str] = Field(None, alias="passwordHash")
    google_id: Optional[str] = Field(None, alias="googleId")

    class Settings:
        name = "users"
        indexes = [
            "apiKeyHash",
            [(("linkedAccounts.platform", 1), ("linkedAccounts.accountId", 1))],
            "email",
            "googleId"
        ]

