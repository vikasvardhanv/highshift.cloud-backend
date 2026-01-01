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
                    res = await twitter.post_tweet(token, req.content)
                    results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                except Exception as post_error:
                    # If 401, try refreshing token once more
                    if "401" in str(post_error) and account.refresh_token_enc:
                        logger.info(f"Got 401 on post, attempting token refresh for {target.accountId}")
                        try:
                            refresh_token = decrypt_token(account.refresh_token_enc)
                            new_tokens = await twitter.refresh_access_token(
                                client_id=os.getenv("TWITTER_CLIENT_ID"),
                                client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
                                refresh_token=refresh_token
                            )
                            token = new_tokens["access_token"]
                            account.access_token_enc = encrypt_token(token)
                            if new_tokens.get("refresh_token"):
                                account.refresh_token_enc = encrypt_token(new_tokens["refresh_token"])
                            account.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=new_tokens.get("expires_in", 7200))
                            await user.save()
                            
                            # Retry post with new token
                            res = await twitter.post_tweet(token, req.content)
                            results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                        except Exception as retry_error:
                            results.append({"platform": "twitter", "status": "failed", "error": str(retry_error)})
                    else:
                        raise post_error
                
            elif target.platform == "instagram":
                # Instagram requires an image URL
                if not req.media:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media URL required for Instagram"})
                    continue
                res = await instagram.publish_image(token, target.accountId, req.media[0], req.content)
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                
            elif target.platform == "facebook":
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
    
    - accounts: JSON array of {platform, accountId} objects
    - content: Post caption/text
    - files: Optional uploaded media files (photos/videos)
    - media_urls: Optional JSON array of media URLs
    """
    try:
        accounts_list = json.loads(accounts)
        urls_list = json.loads(media_urls)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in accounts or media_urls")
    
    # TODO: In production, upload files to cloud storage (S3/Cloudinary) and get URLs
    # For now, we'll note this as a placeholder and use URLs if provided
    
    media = urls_list.copy()
    
    if files:
        for f in files:
            # Placeholder: In production, upload to S3 and append URL
            # For now, we'll add a note that files were received
            logger.info(f"Received file: {f.filename}, size: {f.size}")
            # media.append(uploaded_url)  # Would add real URL here
        
        if not media:
            # If uploads were provided but we can't process them yet
            logger.warning("File uploads received but cloud storage not configured. Use media_urls instead.")
    
    # Create request and delegate to existing logic
    req = MultiPostRequest(
        accounts=[PostAccount(**acc) for acc in accounts_list],
        content=content,
        media=media
    )
    
    return await multi_platform_post(req, user)

