from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from app.utils.auth import get_current_user
from app.models.user import User
from app.platforms import instagram, twitter, facebook, linkedin
from app.services.token_service import decrypt_token
from app.utils.logger import logger
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
async def multi_platform_post(req: MultiPostRequest, user: User = Depends(get_current_user)):
    import os
    import datetime
    import mimetypes
    from app.services.token_service import encrypt_token
    
    results = []
    
    # Determine media type if media exists
    is_video = False
    media_url = None
    media_path = None
    
    if req.local_media_paths and len(req.local_media_paths) > 0:
        media_path = req.local_media_paths[0]
        mime, _ = mimetypes.guess_type(media_path)
        if mime and "video" in mime:
            is_video = True
    elif req.media and len(req.media) > 0:
        media_url = req.media[0]
        # Heuristic check for URL extension if no local path
        ext = media_url.split('?')[0].split('.')[-1].lower()
        if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            is_video = True
            
    logger.info(f"Publishing Content: Video={is_video}, Media={media_url or media_path}")

    # =========================================================================
    # MEDIA HANDLING: Download URLs to temp files if needed (e.g. for Twitter)
    # =========================================================================
    temp_files_to_cleanup = []
    
    # If we have only URLs but need local files (Twitter requires binary upload),
    # download them to temporary paths.
    if not req.local_media_paths and req.media:
        import tempfile
        import os
        import base64
        import re
        
        logger.info(f"No local paths provided. Processing {len(req.media)} media files from URLs...")
        
        try:
            async with httpx.AsyncClient() as client:
                for url in req.media:
                    try:
                        # Check if it's a data URL (base64 encoded)
                        data_url_match = re.match(r'^data:([^;]+);base64,(.+)$', url)
                        
                        if data_url_match:
                            # It's a data URL - decode base64
                            mime_type = data_url_match.group(1)
                            base64_data = data_url_match.group(2)
                            
                            logger.info(f"Processing data URL with MIME type: {mime_type}")
                            
                            # Determine extension from MIME type
                            ext_map = {
                                'image/jpeg': 'jpg',
                                'image/jpg': 'jpg',
                                'image/png': 'png',
                                'image/gif': 'gif',
                                'video/mp4': 'mp4',
                                'video/quicktime': 'mov'
                            }
                            ext = ext_map.get(mime_type, 'tmp')
                            
                            # Create temp file
                            fd, path = tempfile.mkstemp(suffix=f".{ext}")
                            os.close(fd)
                            
                            # Decode and write base64 data
                            media_bytes = base64.b64decode(base64_data)
                            with open(path, "wb") as f:
                                f.write(media_bytes)
                            
                            logger.info(f"Successfully decoded data URL to {path} ({len(media_bytes)} bytes)")
                        else:
                            # It's a regular URL - download via HTTP
                            logger.info(f"Downloading media from: {url[:100]}...")
                            
                            # Guess extension
                            ext = url.split('?')[0].split('.')[-1].lower()
                            if len(ext) > 4 or not ext: 
                                ext = "tmp"
                                
                            # Create temp file
                            fd, path = tempfile.mkstemp(suffix=f".{ext}")
                            os.close(fd)
                            
                            # Download
                            resp = await client.get(url)
                            resp.raise_for_status()
                            
                            content_type = resp.headers.get("content-type", "")
                            if "text/html" in content_type:
                                logger.warning(f"Skipping URL {url} - identified as HTML (likely a webpage link, not media file)")
                                continue
                                
                            with open(path, "wb") as f:
                                f.write(resp.content)
                            
                            logger.info(f"Successfully downloaded URL to {path} ({len(resp.content)} bytes)")
                        
                        if not req.local_media_paths:
                            req.local_media_paths = []
                            
                        req.local_media_paths.append(path)
                        temp_files_to_cleanup.append(path)
                        
                    except Exception as dl_err:
                        logger.error(f"Failed to process media: {dl_err}", exc_info=True)
                        # Continue, maybe other files work or text-only post proceeds
        except Exception as e:
            logger.error(f"Error in media processing block: {e}", exc_info=True)

    for target in req.accounts:

        # Find the linked account in user model
        account = next((a for a in user.linked_accounts if a.platform == target.platform and a.account_id == target.accountId), None)
        
        if not account:
            results.append({"platform": target.platform, "status": "failed", "error": "Account not linked"})
            continue
            
        try:
            token = decrypt_token(account.access_token_enc)
            
            if target.platform == "twitter":
                # Check if token is expired and refresh if needed
                if account.expires_at and account.expires_at < datetime.datetime.utcnow():
                    logger.info(f"Twitter token expired for account {target.accountId}, refreshing...")
                    if account.refresh_token_enc:
                        try:
                            refresh_token = decrypt_token(account.refresh_token_enc)
                            new_tokens = await twitter.refresh_access_token(
                                client_id=os.getenv("TWITTER_CLIENT_ID"),
                                client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
                                refresh_token=refresh_token
                            )
                            # Update stored tokens
                            token = new_tokens["access_token"]
                            account.access_token_enc = encrypt_token(token)
                            if new_tokens.get("refresh_token"):
                                account.refresh_token_enc = encrypt_token(new_tokens["refresh_token"])
                            account.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=new_tokens.get("expires_in", 7200))
                            await user.save()
                            logger.info(f"Twitter token refreshed successfully for account {target.accountId}")
                        except Exception as refresh_error:
                            logger.error(f"Failed to refresh Twitter token: {refresh_error}")
                            results.append({"platform": "twitter", "status": "failed", "error": f"Token expired and refresh failed: {str(refresh_error)}"})
                            continue
                    else:
                        results.append({"platform": "twitter", "status": "failed", "error": "Token expired and no refresh token available. Please reconnect your account."})
                        continue
                
                try:
                    # Upload media if exists
                    media_ids = []
                    if req.local_media_paths:
                        logger.info(f"Twitter: Uploading {len(req.local_media_paths)} media files")
                        for path in req.local_media_paths:
                            try:
                                logger.info(f"Twitter: Uploading file: {path}")
                                # twitter.upload_media requires OAuth 1.0a credentials
                                media_id = await twitter.upload_media(
                                    token,
                                    file_path=path,
                                    api_key=os.getenv("TWITTER_API_KEY"),
                                    api_secret=os.getenv("TWITTER_API_SECRET"),
                                    access_token_oauth1=os.getenv("TWITTER_ACCESS_TOKEN"),
                                    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
                                )
                                media_ids.append(media_id)
                                logger.info(f"Twitter: Successfully uploaded media, ID: {media_id}")
                            except Exception as upload_err:
                                logger.error(f"Failed to upload media to Twitter: {upload_err}", exc_info=True)
                                # Abort immediately if any media upload fails
                                raise upload_err
                    else:
                        logger.warning("Twitter: No local_media_paths provided for media upload")
                    
                    # Safety check: if we expected media but listed none (and didn't raise earlier), abort
                    if req.local_media_paths and not media_ids:
                        raise ValueError("Media upload failed: No media IDs returned despite local paths provided")

                    logger.info(f"Twitter: Creating tweet with {len(media_ids)} media_ids: {media_ids}")
                    res = await twitter.post_tweet(token, req.content, media_ids=media_ids)
                    logger.info(f"Twitter: Tweet created successfully: {res}")
                    results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                except Exception as post_error:
                    logger.error(f"Twitter post failed: {post_error}")
                    results.append({"platform": "twitter", "status": "failed", "error": str(post_error)})
                
            elif target.platform == "instagram":
                # Instagram requires an image/video URL
                if not req.media:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media URL required for Instagram"})
                    continue
                
                # NOTE: This URL must be public. Localhost URLs will fail with Instagram API.
                if is_video:
                    res = await instagram.publish_video(token, target.accountId, req.media[0], req.content)
                else:
                    res = await instagram.publish_image(token, target.accountId, req.media[0], req.content)
                    
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                
            elif target.platform == "facebook":
                if req.media:
                    if is_video:
                         res = await facebook.post_video(token, target.accountId, req.content, req.media[0])
                    else:
                         res = await facebook.post_photo(token, target.accountId, req.content, req.media[0])
                else:
                    res = await facebook.post_to_page(token, target.accountId, req.content)
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                
            elif target.platform == "linkedin":
                if req.media:
                    media_type_str = "video" if is_video else "image"
                    
                    # 1. Register Upload
                    reg_res = await linkedin.register_upload(token, target.accountId, media_type=media_type_str)
                    upload_url = reg_res['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                    asset_urn = reg_res['value']['asset']
                    
                    # 2. Upload Binary
                    image_data = None
                    # Prefer local path if available to avoid network roundtrip
                    if req.local_media_paths:
                        with open(req.local_media_paths[0], "rb") as f:
                            image_data = f.read()
                    elif req.media:
                        # Download from URL
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(req.media[0])
                            resp.raise_for_status()
                            image_data = resp.content
                            
                    if image_data:
                        await linkedin.upload_asset(upload_url, image_data, token)
                        
                        # 3. Create Post
                        res = await linkedin.post_with_media(token, target.accountId, req.content, asset_urn, media_type=media_type_str)
                    else:
                        # Fallback if binary data loading failed
                        res = await linkedin.post_to_profile(token, target.accountId, req.content)
                else:
                    res = await linkedin.post_to_profile(token, target.accountId, req.content)
                results.append({"platform": "linkedin", "status": "success", "id": res.get("id")})
                
            else:
                results.append({"platform": target.platform, "status": "failed", "error": "Platform publishing not implemented yet"})
                
        except Exception as e:
            logger.error(f"Failed to post to {target.platform}: {e}")
            results.append({"platform": target.platform, "status": "failed", "error": str(e)})
            
    # Cleanup temporary files
    if 'temp_files_to_cleanup' in locals():
        import os
        for path in temp_files_to_cleanup:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"Cleaned up temp file: {path}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to cleanup temp file {path}: {cleanup_err}")

    return {"results": results}


# ============ NEW: File Upload Endpoint ============
@router.post("/upload")
async def upload_and_post(
    accounts: str = Form(...),  # JSON string of accounts array
    content: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    media_urls: str = Form(default="[]"),  # JSON string of URL array
    user: User = Depends(get_current_user)
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
    user: User = Depends(get_current_user)
):
    """
    Upload media files, persist them in the database (Media model), and return their URLs.
    Handles Cloudinary (if configured) or base64 storage as fallback.
    """
    import shutil
    import uuid
    import os
    import base64
    from app.models.media import Media
    
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

            # 4. Save to Database
            media_doc = Media(
                userId=str(user.id),
                filename=f.filename,
                contentType=f.content_type or f"image/{ext}",
                fileType="image" if "image" in (f.content_type or "") else "video",
                cloudUrl=final_cloud_url,
                dataUrl=final_data_url, # Warning: This can be large. Ideally use S3/GridFS.
                localPath=final_local_path,
                sizeBytes=len(content)
            )
            await media_doc.insert()
            
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
    user: User = Depends(get_current_user)
):
    """
    Fetch user's media library.
    """
    from app.models.media import Media
    
    docs = await Media.find(
        {"userId": str(user.id)}
    ).sort(-Media.created_at).limit(limit).skip(skip).to_list()
    
    return {
        "media": [
            {
                "id": str(m.id),
                "url": m.get_display_url(),
                "filename": m.filename,
                "type": m.file_type,
                "created_at": m.created_at
            }
            for m in docs
        ]
    }

@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str,
    user: User = Depends(get_current_user)
):
    """
    Delete a media item from the library.
    """
    from app.models.media import Media
    from beanie import PydanticObjectId
    
    try:
        obj_id = PydanticObjectId(media_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid media ID format")
    
    media = await Media.find_one({"_id": obj_id, "userId": str(user.id)})
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
        
    await media.delete()
    logger.info(f"Deleted media {media_id} for user {user.id}")
    
    return {"status": "success", "id": media_id}
