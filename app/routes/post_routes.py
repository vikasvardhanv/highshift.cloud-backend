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
    from app.services.token_service import encrypt_token
    
    results = []
    
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
                        for path in req.local_media_paths:
                            try:
                                media_id = await twitter.upload_media(token, file_path=path)
                                media_ids.append(media_id)
                            except Exception as upload_err:
                                logger.error(f"Failed to upload media to Twitter: {upload_err}")
                    
                    res = await twitter.post_tweet(token, req.content, media_ids=media_ids)
                    results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                except Exception as post_error:
                    # If 401, try refreshing token once more (Simplified for brevity, same logic as above)
                    # For now just logging error to avoid deep nesting complexity in this edit
                    logger.error(f"Twitter post failed: {post_error}")
                    results.append({"platform": "twitter", "status": "failed", "error": str(post_error)})
                
            elif target.platform == "instagram":
                # Instagram requires an image URL
                if not req.media:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media URL required for Instagram"})
                    continue
                # Use the first media URL
                # NOTE: This URL must be public. Localhost URLs will fail with Instagram API.
                res = await instagram.publish_image(token, target.accountId, req.media[0], req.content)
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                
            elif target.platform == "facebook":
                if req.media:
                    # Use first image for now
                    res = await facebook.post_photo(token, target.accountId, req.content, req.media[0])
                else:
                    res = await facebook.post_to_page(token, target.accountId, req.content)
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                
            elif target.platform == "linkedin":
                if req.media:
                    # 1. Register Upload
                    reg_res = await linkedin.register_upload(token, target.accountId)
                    upload_url = reg_res['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                    asset_urn = reg_res['value']['asset']
                    
                    # 2. Upload Image
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
                        await linkedin.upload_image(upload_url, image_data, token)
                        
                        # 3. Create Post
                        res = await linkedin.post_with_media(token, target.accountId, req.content, asset_urn)
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
    Upload media files and return their public URLs (for scheduling or drafts).
    On serverless (e.g., Vercel), filesystem is read-only except /tmp.
    This endpoint attempts to save to /tmp and returns base64 data URLs as fallback.
    
    For production with Instagram/Facebook (which require public URLs),
    configure CLOUDINARY_URL or AWS S3 in environment variables.
    """
    import shutil
    import uuid
    import os
    import base64
    
    uploaded_urls = []
    local_paths = []  # For platforms like Twitter that support file uploads
    
    # Check if Cloudinary is configured
    cloudinary_url = os.getenv("CLOUDINARY_URL")
    
    for f in files:
        try:
            # Read file content
            content = await f.read()
            ext = f.filename.split('.')[-1] if '.' in f.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            
            if cloudinary_url:
                # Use Cloudinary for cloud storage
                try:
                    import cloudinary
                    import cloudinary.uploader
                    
                    # Configure from URL
                    cloudinary.config(cloudinary_url=cloudinary_url)
                    
                    # Upload to Cloudinary
                    result = cloudinary.uploader.upload(
                        content,
                        public_id=filename.rsplit('.', 1)[0],
                        resource_type="auto"
                    )
                    uploaded_urls.append(result['secure_url'])
                    logger.info(f"Uploaded to Cloudinary: {result['secure_url']}")
                    continue
                except ImportError:
                    logger.warning("Cloudinary package not installed. Falling back to local storage.")
                except Exception as cloud_err:
                    logger.error(f"Cloudinary upload failed: {cloud_err}")
            
            # Try /tmp directory (works on serverless)
            tmp_dir = "/tmp/uploads"
            try:
                os.makedirs(tmp_dir, exist_ok=True)
                file_path = os.path.join(tmp_dir, filename)
                
                with open(file_path, "wb") as buffer:
                    buffer.write(content)
                
                local_paths.append(file_path)
                
                # For Twitter, we can use the local path directly
                # For other platforms, they need a public URL
                # Generate a base64 data URL as fallback for preview purposes
                mime_type = f.content_type or f"image/{ext}"
                base64_data = base64.b64encode(content).decode('utf-8')
                data_url = f"data:{mime_type};base64,{base64_data}"
                
                uploaded_urls.append(data_url)
                logger.info(f"Saved file to {file_path}, generated data URL")
                
            except OSError as e:
                logger.warning(f"Failed to save to /tmp: {e}, using data URL only")
                # Generate base64 data URL as last resort
                mime_type = f.content_type or f"image/{ext}"
                base64_data = base64.b64encode(content).decode('utf-8')
                data_url = f"data:{mime_type};base64,{base64_data}"
                uploaded_urls.append(data_url)
                
        except Exception as e:
            logger.error(f"Failed to process file {f.filename}: {e}")
            
    return {
        "urls": uploaded_urls,
        "localPaths": local_paths,  # For Twitter uploads
        "warning": "For Instagram/Facebook posting, configure CLOUDINARY_URL for public URLs" if not cloudinary_url else None
    }

