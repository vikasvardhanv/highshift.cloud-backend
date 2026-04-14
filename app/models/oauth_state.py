from datetime import datetime
import os
from typing import Optional
from beanie import Document
from pydantic import Field
from app.db.postgres import (
    delete_oauth_state,
    get_oauth_state,
    insert_oauth_state,
    is_postgres_url,
)

class OAuthState(Document):
    state_id: str = Field(unique=True)
    code_verifier: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "oauth_states"
        indexes = ["state_id"]

    @staticmethod
    def _use_postgres() -> bool:
        return is_postgres_url(os.getenv("DATABASE_URL"))

    @classmethod
    async def find_one(cls, query):  # type: ignore[override]
        if not cls._use_postgres():
            return await super().find_one(query)
        state_id = query.get("state_id")
        if not state_id:
            return None
        row = await get_oauth_state(state_id)
        if not row:
            return None
        return OAuthState(
            state_id=row.get("state_id"),
            code_verifier=row.get("code_verifier"),
            extra_data=row.get("extra_data") or {},
            created_at=row.get("created_at"),
        )

    async def insert(self, *args, **kwargs):  # type: ignore[override]
        if not self._use_postgres():
            return await super().insert(*args, **kwargs)
        await insert_oauth_state(self.state_id, self.code_verifier, self.extra_data)
        return self

    async def delete(self, *args, **kwargs):  # type: ignore[override]
        if not self._use_postgres():
            return await super().delete(*args, **kwargs)
        await delete_oauth_state(self.state_id)
        return None
