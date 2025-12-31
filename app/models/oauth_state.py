from datetime import datetime
from beanie import Document
from pydantic import Field

class OAuthState(Document):
    state_id: str = Field(unique=True)
    code_verifier: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "oauth_states"
        indexes = ["state_id"]
