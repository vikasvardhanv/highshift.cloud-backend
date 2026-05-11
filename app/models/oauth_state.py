from datetime import datetime
import json
import os
import logging
from typing import Any, NamedTuple
from typing import Optional
from beanie import Document
from pydantic import Field, field_validator
from app.db.postgres import (
    delete_oauth_state,
    get_oauth_state,
    insert_oauth_state,
    is_postgres_url,
)

logger = logging.getLogger(__name__)


class OAuthStateData(NamedTuple):
    """Lightweight data class for PostgreSQL-backed OAuthState"""
    state_id: str
    code_verifier: Optional[str]
    extra_data: dict
    created_at: datetime

class OAuthState(Document):
    state_id: str = Field(unique=True)
    code_verifier: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('extra_data', mode='before')
    @classmethod
    def normalize_extra_data(cls, v: Any) -> dict:
        """Normalize extra_data from string or dict to dict"""
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}


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
        # Normalize extra_data before returning
        extra_data = row.get("extra_data")
        logger.debug(f"OAuthState.find_one: raw extra_data type={type(extra_data).__name__}, value={extra_data}")
        
        if isinstance(extra_data, str):
            try:
                extra_data = json.loads(extra_data)
                logger.debug(f"OAuthState.find_one: parsed JSON string to dict")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"OAuthState.find_one: failed to parse JSON string: {e}")
                extra_data = {}
        elif not isinstance(extra_data, dict):
            logger.warning(f"OAuthState.find_one: extra_data is {type(extra_data).__name__}, converting to dict")
            extra_data = {}
        
        result = OAuthStateData(
            state_id=row.get("state_id"),
            code_verifier=row.get("code_verifier"),
            extra_data=extra_data,
            created_at=row.get("created_at"),
        )
        logger.debug(f"OAuthState.find_one: returning OAuthStateData with extra_data type={type(result.extra_data).__name__}")
        return result

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
