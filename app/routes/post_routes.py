from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from app.utils.auth import get_current_user
from app.models.user import User
from app.platforms import instagram, twitter, facebook, linkedin
from app.services.token_service import decrypt_token
from app.utils.logger import logger
import json

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
                # Facebook supports photos edge, but for simplicity using feed with link if no files
                # If we have media, ideally use photos edge. 
                # For now using the basic implementation: Text + Link (if strictly URL)
                # Improving: If we have media URL, send it as link? 
                # Facebook feed "link" parameter expects a webpage, but "picture" or "source" is for images.
                # Staying safe: sending content.
                res = await facebook.post_to_page(token, target.accountId, req.content)
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                
            elif target.platform == "linkedin":
                # LinkedIn URN needed, normally stored in rawProfile or as account_id
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
            os.makedirs(upload_dir)
            
        for f in files:
            # Generate unique filename
            ext = f.filename.split('.')[-1] if '.' in f.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(upload_dir, filename)
            
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
    
    # Create request and delegate to existing logic
    req = MultiPostRequest(
        accounts=[PostAccount(**acc) for acc in accounts_list],
        content=content,
        media=media,
        local_media_paths=local_paths
    )
    
    return await multi_platform_post(req, user)

