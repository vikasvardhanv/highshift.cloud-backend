"""
Media Routes - Upload and serve media for Instagram, TikTok, and other platforms.
Supports both PostgreSQL (primary) and MongoDB Beanie (fallback).
"""
import os
import uuid
import base64
import logging
import mimetypes
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.user import User
from app.routes.auth_routes import get_optional_user

router = APIRouter(prefix="/api/media", tags=["Media"])
logger = logging.getLogger("media")

# In-memory ephemeral fallback cache for served media
_ephemeral_media_cache = {}


class UploadMediaRequest(BaseModel):
    data_url: str  # Base64 data URL
    filename: Optional[str] = "upload"


class UploadMediaResponse(BaseModel):
    media_id: str
    public_url: str
    content_type: str


@router.post("/upload", response_model=UploadMediaResponse)
async def upload_media(
    request: UploadMediaRequest,
    user: Optional[User] = Depends(get_optional_user)
):
    """
    Upload media and get a public URL for social publishing.
    Accepts base64 data URL, stores in PostgreSQL (or MongoDB/cache), returns public URL.
    """
    try:
        data_url = request.data_url
        if not data_url.startswith("data:"):
            raise HTTPException(status_code=400, detail="Invalid data URL format. Must start with 'data:'")

        header, encoded = data_url.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        file_type = "video" if "video" in mime_type else "image"
        decoded_data = base64.b64decode(encoded)
        size_bytes = len(decoded_data)
        
        media_id = uuid.uuid4().hex
        user_id = str(user.id) if user and hasattr(user, "id") and user.id else None

        # 1. Try PostgreSQL primary storage
        saved_in_db = False
        try:
            from app.db.postgres import get_pool
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Check if user_id is a valid UUID or fallback to anonymous system user
                    uid_val = None
                    if user_id:
                        try:
                            import uuid as _u
                            uid_val = str(_u.UUID(user_id))
                        except Exception:
                            uid_val = None
                    
                    if uid_val:
                        await conn.execute(
                            """
                            INSERT INTO media_assets (id, user_id, filename, content_type, file_type, data_url, size_bytes)
                            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                            """,
                            uuid.UUID(media_id),
                            uuid.UUID(uid_val),
                            request.filename or "upload",
                            mime_type,
                            file_type,
                            data_url,
                            size_bytes,
                        )
                        saved_in_db = True
        except Exception as pg_err:
            logger.warning(f"Postgres media asset insert skipped/failed: {pg_err}")

        # 2. Try MongoDB fallback if Beanie is active
        if not saved_in_db:
            try:
                from app.models.media import Media
                media = Media(
                    media_id=media_id,
                    user_id=user_id or "anonymous",
                    filename=request.filename or "upload",
                    content_type=mime_type,
                    file_type=file_type,
                    data_url=data_url,
                    size_bytes=size_bytes
                )
                await media.insert()
                saved_in_db = True
            except Exception:
                pass

        # 3. Always keep in ephemeral cache as instant fast-path
        _ephemeral_media_cache[media_id] = {
            "content_type": mime_type,
            "data": decoded_data,
            "data_url": data_url
        }

        backend_url = os.getenv("BACKEND_URL", "https://api.socialraven.online")
        public_url = f"{backend_url}/api/media/{media_id}"
        
        logger.info(f"Media uploaded successfully: {media_id} -> {public_url}")

        return UploadMediaResponse(
            media_id=media_id,
            public_url=public_url,
            content_type=mime_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Media upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload media: {str(e)}")


@router.get("/{media_id}")
async def serve_media(media_id: str):
    """
    Serve media by ID. Returns the raw image/video with proper content-type.
    Publicly accessible so social platforms can fetch media assets.
    """
    # 1. Check ephemeral cache
    if media_id in _ephemeral_media_cache:
        item = _ephemeral_media_cache[media_id]
        return Response(
            content=item["data"],
            media_type=item["content_type"],
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            }
        )

    # 2. Check PostgreSQL
    try:
        from app.db.postgres import get_pool
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT data_url, content_type FROM media_assets WHERE id::text = $1",
                    media_id
                )
                if row and row.get("data_url"):
                    header, encoded = row["data_url"].split(",", 1)
                    decoded_data = base64.b64decode(encoded)
                    return Response(
                        content=decoded_data,
                        media_type=row.get("content_type") or "image/png",
                        headers={
                            "Cache-Control": "public, max-age=86400",
                            "Access-Control-Allow-Origin": "*"
                        }
                    )
    except Exception as pg_err:
        logger.warning(f"Failed to fetch media from Postgres: {pg_err}")

    # 3. Check MongoDB
    try:
        from app.models.media import Media
        media = await Media.find_one({"media_id": media_id})
        if media and media.data_url:
            header, encoded = media.data_url.split(",", 1)
            decoded_data = base64.b64decode(encoded)
            return Response(
                content=decoded_data,
                media_type=media.content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception as mongo_err:
        logger.warning(f"Failed to fetch media from MongoDB: {mongo_err}")

    raise HTTPException(status_code=404, detail="Media not found")
