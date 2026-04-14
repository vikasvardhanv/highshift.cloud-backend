from datetime import datetime
import uuid
from typing import List, Optional
import os
from beanie import Document
from pydantic import BaseModel, Field
from app.db.postgres import (
    fetch_user_by_email_ci,
    fetch_user_by_google_or_email,
    fetch_user_by_id,
    fetch_user_by_linked_account,
    insert_user,
    is_postgres_url,
    update_user,
)

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
    profile_id: Optional[str] = Field(None, alias="profileId") # ID of the Profile this account belongs to

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
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class User(Document):
    api_key_hash: str = Field(unique=True, alias="apiKeyHash")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    api_keys: List[ApiKey] = Field(default=[], alias="apiKeys")
    linked_accounts: List[LinkedAccount] = Field(default=[], alias="linkedAccounts")
    profiles: List[Profile] = Field(default=[], alias="profiles")
    developer_keys: dict = Field(default={}, alias="developerKeys")
    
    # B2B / Limits
    plan_tier: str = Field(default="starter", alias="planTier")
    max_profiles: int = Field(default=50, alias="maxProfiles")

    # New Auth Fields
    email: Optional[str] = Field(None, unique=True)
    password_hash: Optional[str] = Field(None, alias="passwordHash")
    google_id: Optional[str] = Field(None, alias="googleId")
    
    # Password Reset
    reset_token: Optional[str] = Field(None, alias="resetToken")
    reset_token_expiry: Optional[datetime] = Field(None, alias="resetTokenExpiry")

    class Settings:
        name = "users"
        indexes = [
            "apiKeyHash",
            [("linkedAccounts.platform", 1), ("linkedAccounts.accountId", 1)],
            "email",
            "googleId"
        ]

    @staticmethod
    def _use_postgres() -> bool:
        return is_postgres_url(os.getenv("DATABASE_URL"))

    @staticmethod
    def _from_row(row: dict) -> "User":
        return User(
            id=str(row.get("id")),
            apiKeyHash=row.get("api_key_hash"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            apiKeys=row.get("api_keys") or [],
            linkedAccounts=row.get("linked_accounts") or [],
            profiles=row.get("profiles") or [],
            developerKeys=row.get("developer_keys") or {},
            planTier=row.get("plan_tier") or "starter",
            maxProfiles=row.get("max_profiles") or 50,
            email=row.get("email"),
            passwordHash=row.get("password_hash"),
            googleId=row.get("google_id"),
        )

    @classmethod
    async def get(cls, id):  # type: ignore[override]
        if not cls._use_postgres():
            return await super().get(id)
        row = await fetch_user_by_id(str(id))
        return cls._from_row(row) if row else None

    @classmethod
    async def find_one(cls, query):  # type: ignore[override]
        if not cls._use_postgres():
            return await super().find_one(query)

        row = None
        if "email" in query and isinstance(query["email"], dict) and "$regex" in query["email"]:
            email = query["email"]["$regex"].strip("^$")
            row = await fetch_user_by_email_ci(email)
        elif "$or" in query:
            opts = query["$or"]
            # google/email query
            google = None
            email = None
            for o in opts:
                if "googleId" in o:
                    google = o["googleId"]
                if "email" in o:
                    email = o["email"]
            if google is not None and email is not None:
                row = await fetch_user_by_google_or_email(google, email)
        elif "linkedAccounts.platform" in query and "linkedAccounts.accountId" in query:
            platform = query["linkedAccounts.platform"]
            acc = query["linkedAccounts.accountId"]
            if isinstance(acc, dict) and "$in" in acc and acc["$in"]:
                # return first match across candidate ids
                for candidate in acc["$in"]:
                    row = await fetch_user_by_linked_account(platform, candidate)
                    if row:
                        break
            else:
                row = await fetch_user_by_linked_account(platform, acc)

        return cls._from_row(row) if row else None

    async def insert(self, *args, **kwargs):  # type: ignore[override]
        if not self._use_postgres():
            return await super().insert(*args, **kwargs)
        row = await insert_user(
            {
                "id": str(getattr(self, "id", "") or uuid.uuid4()),
                "email": self.email,
                "password_hash": self.password_hash,
                "google_id": self.google_id,
                "api_key_hash": self.api_key_hash,
                "api_keys": [k.model_dump(by_alias=True) for k in (self.api_keys or [])],
                "linked_accounts": [a.model_dump(by_alias=True) for a in (self.linked_accounts or [])],
                "profiles": [p.model_dump(by_alias=True) for p in (self.profiles or [])],
                "developer_keys": self.developer_keys or {},
                "plan_tier": self.plan_tier,
                "max_profiles": self.max_profiles,
            }
        )
        self.id = str(row["id"])
        return self

    async def save(self, *args, **kwargs):  # type: ignore[override]
        if not self._use_postgres():
            return await super().save(*args, **kwargs)
        row = await update_user(
            str(self.id),
            {
                "id": str(self.id),
                "email": self.email,
                "password_hash": self.password_hash,
                "google_id": self.google_id,
                "api_key_hash": self.api_key_hash,
                "api_keys": [
                    k.model_dump(by_alias=True) if hasattr(k, "model_dump") else k
                    for k in (self.api_keys or [])
                ],
                "linked_accounts": [
                    a.model_dump(by_alias=True) if hasattr(a, "model_dump") else a
                    for a in (self.linked_accounts or [])
                ],
                "profiles": [
                    p.model_dump(by_alias=True) if hasattr(p, "model_dump") else p
                    for p in (self.profiles or [])
                ],
                "developer_keys": self.developer_keys or {},
                "plan_tier": self.plan_tier,
                "max_profiles": self.max_profiles,
            },
        )
        return self
