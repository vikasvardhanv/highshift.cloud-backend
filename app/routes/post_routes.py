from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from app.utils.auth import get_current_user, AuthUser
from app.platforms import instagram, twitter, facebook, linkedin
from app.services.token_service import decrypt_token
from app.utils.logger import logger
from app.db.postgres import insert_media_asset, list_media_assets, delete_media_asset
import json
import httpx

router = APIRouter(prefix="/post", tags=["Publishing"])

class PostAccount(BaseModel):
    platform: str
    accountId: str

class MultiPostRequest(BaseModel):
    accounts: List[PostAccount]
    content: str
    media: Optional[List[str]] = []
    local_media_paths: Optional[List[str]] = [] # For internal use (Twitter uploads)

@router.post("/multi")
async def multi_platform_post(req: MultiPostRequest, user: AuthUser = Depends(get_current_user)):
    from app.services.publishing_service import publish_content
    
    # Transform Pydantic models to list of dicts for the service
    accounts_list = [{"platform": acc.platform, "accountId": acc.accountId} for acc in req.accounts]
    
    result = await publish_content(
        user=user,
        content=req.content,
        accounts=accounts_list,
        media_urls=req.media,
        local_media_paths=req.local_media_paths
    )
    
    return result


# ============ NEW: File Upload Endpoint ============
@router.post("/upload")
async def upload_and_post(
    accounts: str = Form(...),  # JSON string of accounts array
    content: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    media_urls: str = Form(default="[]"),  # JSON string of URL array
    user: AuthUser = Depends(get_current_user)
):
    """
    Upload media files or provide URLs, then publish to selected platforms.
    """
    import shutil
    import uuid
    import os
    
    try:
        accounts_list = json.loads(accounts)
        urls_list = json.loads(media_urls)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in accounts or media_urls")
    
    media = urls_list.copy()
    local_paths = []
    
    if files:
        upload_dir = "app/static/uploads"
        # Ensure dir exists (redundant check but safe)
        if not os.path.exists(upload_dir):
            try:
                os.makedirs(upload_dir)
            except OSError as e:
                logger.error(f"Could not create upload directory: {e}")
                # Fallback: Depending on needs, we might want to raise HTTPException
                # or just continue. If we continue, file saving will fail.
        
        for f in files:
            # Generate unique filename
            ext = f.filename.split('.')[-1] if '.' in f.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(upload_dir, filename)
            
            try:
                # Save file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)
                
                # Add to local paths for Twitter
                local_paths.append(file_path)
                
                # Add to media URLs for others (Warning: Localhost URLs won't work for Insta/FB API)
                # Assuming backend runs on port 3000 or similar. In prod, this should be the public domain.
                # Using relative path? APIs need absolute http/s.
                domain = os.getenv("API_BASE_URL", "http://localhost:3000") 
                public_url = f"{domain}/static/uploads/{filename}"
                media.append(public_url)
                
                logger.info(f"Saved file to {file_path}, Public URL: {public_url}")
            except OSError as e:
                logger.error(f"Failed to save file (FileSystem Read-only?): {e}")
                # We can't proceed with this file
                continue
    
    # Create request and delegate to existing logic
    req = MultiPostRequest(
        accounts=[PostAccount(**acc) for acc in accounts_list],
        content=content,
        media=media,
        local_media_paths=local_paths
    )
    
    return await multi_platform_post(req, user)

@router.post("/media-upload")
async def upload_media_only(
    files: List[UploadFile] = File(...),
    user: AuthUser = Depends(get_current_user)
):
    """
    Upload media files, persist them in the database (Media model), and return their URLs.
    Handles Cloudinary (if configured) or base64 storage as fallback.
    """
    import shutil
    import uuid
    import os
    import base64
    
    uploaded_urls = []
    local_paths = [] 
    
    cloudinary_url = os.getenv("CLOUDINARY_URL")
    
    for f in files:
        try:
            content = await f.read()
            ext = f.filename.split('.')[-1] if '.' in f.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            
            # Defaults
            final_cloud_url = None
            final_data_url = None
            final_local_path = None
            
            # 1. Try Cloudinary
            if cloudinary_url:
                try:
                    import cloudinary
                    import cloudinary.uploader
                    cloudinary.config(cloudinary_url=cloudinary_url)
                    result = cloudinary.uploader.upload(
                        content,
                        public_id=filename.rsplit('.', 1)[0],
                        resource_type="auto"
                    )
                    final_cloud_url = result['secure_url']
                    uploaded_urls.append(final_cloud_url)
                except Exception as e:
                    logger.error(f"Cloudinary upload failed: {e}")

            # 2. If no cloud URL, use Base64 (Data URL) storage
            if not final_cloud_url:
                mime_type = f.content_type or f"image/{ext}"
                base64_data = base64.b64encode(content).decode('utf-8')
                final_data_url = f"data:{mime_type};base64,{base64_data}"
                uploaded_urls.append(final_data_url)
            
            # 3. Handle Local Path (for Twitter/server-side clients that might need file access)
            # On serverless, this is ephemeral (/tmp), but better than nothing for immediate processing
            tmp_dir = "/tmp/uploads"
            try:
                os.makedirs(tmp_dir, exist_ok=True)
                file_path = os.path.join(tmp_dir, filename)
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
                final_local_path = file_path
                local_paths.append(file_path)
            except Exception:
                pass

            await insert_media_asset(
                user_id=str(user.id),
                filename=f.filename,
                content_type=f.content_type or f"image/{ext}",
                file_type="image" if "image" in (f.content_type or "") else "video",
                cloud_url=final_cloud_url,
                data_url=final_data_url,
                local_path=final_local_path,
                size_bytes=len(content),
            )
            
        except Exception as e:
            logger.error(f"Failed to process file {f.filename}: {e}")
            
    return {
        "urls": uploaded_urls,
        "local_paths": local_paths,
        "cloudinary_configured": bool(cloudinary_url)
    }

@router.get("/media/library")
async def get_media_library(
    limit: int = 50,
    skip: int = 0,
    user: AuthUser = Depends(get_current_user)
):
    """
    Fetch user's media library.
    """
    docs = await list_media_assets(str(user.id), limit=limit, skip=skip)
    
    return {
        "media": [
            {
                "id": str(m["id"]),
                "url": m.get("cloud_url") or m.get("data_url") or m.get("local_path"),
                "filename": m.get("filename"),
                "type": m.get("file_type"),
                "created_at": m.get("created_at"),
            }
            for m in docs
        ]
    }

@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Delete a media item from the library.
    """
    ok = await delete_media_asset(str(user.id), media_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Media not found")

    logger.info(f"Deleted media {media_id} for user {user.id}")
    
    return {"status": "success", "id": media_id}
