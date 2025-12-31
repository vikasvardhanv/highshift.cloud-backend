from datetime import datetime
from typing import List, Optional
from beanie import Document, Link
from pydantic import Field, BaseModel
from .user import User

class BrandDocument(BaseModel):
    name: str
    url: str
    doc_type: str = Field(alias="type")

class BrandKit(Document):
    user_id: Link[User] = Field(alias="userId")
    name: str = "My Brand"
    voice_description: str = Field("", alias="voiceDescription")
    website: str = ""
    colors: List[str] = Field(default=[])
    documents: List[BrandDocument] = Field(default=[])
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "brand_kits"
        indexes = ["userId"]
