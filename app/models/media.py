from datetime import datetime
import uuid
from typing import Optional
from beanie import Document
from pydantic import Field

class Media(Document):
    """Stores uploaded media files in the database."""
    user_id: str = Field(alias="userId")
    filename: str
    content_type: str = Field(alias="contentType")  # e.g., "image/jpeg", "video/mp4"
    file_type: str = Field(alias="fileType")  # "image" or "video"
    
    # Store base64 encoded data for small files, or URL for cloud storage
    data_url: Optional[str] = Field(None, alias="dataUrl")  # base64 data URL for display
    cloud_url: Optional[str] = Field(None, alias="cloudUrl")  # Cloudinary/S3 URL if available
    local_path: Optional[str] = Field(None, alias="localPath")  # /tmp path (ephemeral on serverless)
    
    # Metadata
    size_bytes: Optional[int] = Field(None, alias="sizeBytes")
    width: Optional[int] = None
    height: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    
    class Settings:
        name = "media"
        indexes = [
            "userId",
            "createdAt"
        ]
    
    def get_display_url(self) -> str:
        """Return the best available URL for display."""
        return self.cloud_url or self.data_url or ""
