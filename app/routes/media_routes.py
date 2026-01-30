"""
Media Routes - Upload and serve media for Instagram and other platforms.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import base64
import mimetypes
import logging

from app.models.media import Media
from app.models.user import User
from app.routes.auth_routes import get_optional_user

router = APIRouter(prefix="/api/media", tags=["Media"])
logger = logging.getLogger("media")


class UploadMediaRequest(BaseModel):
    """Request body for media upload."""
    data_url: str  # Base64 data URL like "data:image/jpeg;base64,..."
    filename: Optional[str] = "upload"


class UploadMediaResponse(BaseModel):
    """Response with the public URL."""
    media_id: str
    public_url: str
    content_type: str


@router.post("/upload", response_model=UploadMediaResponse)
async def upload_media(
    request: UploadMediaRequest,
    user: User = Depends(get_optional_user)
):
    """
    Upload media and get a public URL for Instagram/social publishing.
    Accepts base64 data URL, stores in MongoDB, returns public URL.
    """
    try:
        data_url = request.data_url
        
        # Parse data URL
        if not data_url.startswith("data:"):
            raise HTTPException(status_code=400, detail="Invalid data URL format. Must start with 'data:'")
        
        # Extract mime type and base64 data
        header, encoded = data_url.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        
        # Determine file type
        file_type = "video" if "video" in mime_type else "image"
        
        # Calculate size
        decoded_data = base64.b64decode(encoded)
        size_bytes = len(decoded_data)
        
        # Create media document
        media = Media(
            user_id=str(user.id) if user else "anonymous",
            filename=request.filename,
            content_type=mime_type,
            file_type=file_type,
            data_url=data_url,
            size_bytes=size_bytes
        )
        
        await media.insert()
        
        public_url = media.get_public_url()
        
        logger.info(f"Media uploaded: {media.media_id} -> {public_url}")
        
        return UploadMediaResponse(
            media_id=media.media_id,
            public_url=public_url,
            content_type=mime_type
        )
        
    except Exception as e:
        logger.error(f"Media upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload media: {str(e)}")


@router.get("/{media_id}")
async def serve_media(media_id: str):
    """
    Serve media by ID. Returns the raw image/video with proper content-type.
    This endpoint is publicly accessible so Instagram can fetch from it.
    """
    try:
        media = await Media.find_one({"media_id": media_id})
        
        if not media:
            raise HTTPException(status_code=404, detail="Media not found")
        
        if not media.data_url:
            raise HTTPException(status_code=404, detail="Media data not available")
        
        # Parse and decode the base64 data
        header, encoded = media.data_url.split(",", 1)
        decoded_data = base64.b64decode(encoded)
        
        return Response(
            content=decoded_data,
            media_type=media.content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 1 day
                "Access-Control-Allow-Origin": "*"  # Allow Instagram to fetch
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve media {media_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve media")
