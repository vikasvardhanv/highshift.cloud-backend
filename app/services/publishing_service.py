import os
import datetime
import mimetypes
import logging
import tempfile
import base64
import re
import httpx
from typing import List, Optional, Dict, Any

from app.models.user import User
from app.models.activity import ActivityLog
from app.services.token_service import decrypt_token, encrypt_token
from app.platforms import instagram, twitter, facebook, linkedin, tiktok

logger = logging.getLogger("publishing")

async def publish_content(
    user: User, 
    content: str, 
    accounts: List[Dict[str, str]], # List of {platform, accountId}
    media_urls: List[str] = [], 
    local_media_paths: List[str] = []
) -> Dict[str, Any]:
    """
    Publishes content to multiple social media accounts.
    Returns a dict with results.
    """
    results = []
    
    # Determine media type if media exists
    is_video = False
    media_url = None
    media_path = None
    
    if local_media_paths and len(local_media_paths) > 0:
        media_path = local_media_paths[0]
        mime, _ = mimetypes.guess_type(media_path)
        if mime and "video" in mime:
            is_video = True
    elif media_urls and len(media_urls) > 0:
        media_url = media_urls[0]
        # Heuristic check for URL extension if no local path
        ext = media_url.split('?')[0].split('.')[-1].lower()
        if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            is_video = True
            
    logger.info(f"Publishing Content (User {user.id}): Video={is_video}, Media={media_url or media_path}")

    # =========================================================================
    # MEDIA HANDLING: Download URLs to temp files if needed (e.g. for Twitter)
    # =========================================================================
    temp_files_to_cleanup = []
    
    # If we have only URLs but might need local files (Twitter requires binary upload),
    # download them to temporary paths.
    if not local_media_paths and media_urls:
        logger.info(f"No local paths provided. Processing {len(media_urls)} media files from URLs...")
        local_media_paths = [] # Initialize if None
        
        try:
            async with httpx.AsyncClient() as client:
                for url in media_urls:
                    try:
                        # Check if it's a data URL (base64 encoded)
                        data_url_match = re.match(r'^data:([^;]+);base64,(.+)$', url)
                        
                        if data_url_match:
                            # It's a data URL - decode base64
                            mime_type = data_url_match.group(1)
                            base64_data = data_url_match.group(2)
                            
                            # Determine extension from MIME type
                            ext_map = {
                                'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/png': 'png',
                                'image/gif': 'gif', 'video/mp4': 'mp4', 'video/quicktime': 'mov'
                            }
                            ext = ext_map.get(mime_type, 'tmp')
                            
                            # Create temp file
                            fd, path = tempfile.mkstemp(suffix=f".{ext}")
                            os.close(fd)
                            
                            # Decode and write base64 data
                            media_bytes = base64.b64decode(base64_data)
                            with open(path, "wb") as f:
                                f.write(media_bytes)
                                
                            logger.info(f"Successfully decoded data URL to {path}")
                        else:
                            # It's a regular URL - download via HTTP
                            # Guess extension
                            ext = url.split('?')[0].split('.')[-1].lower()
                            if len(ext) > 4 or not ext: 
                                ext = "tmp"
                                
                            # Create temp file
                            fd, path = tempfile.mkstemp(suffix=f".{ext}")
                            os.close(fd)
                            
                            # Download
                            resp = await client.get(url, timeout=30.0)
                            resp.raise_for_status()
                            
                            content_type = resp.headers.get("content-type", "")
                            if "text/html" in content_type:
                                logger.warning(f"Skipping URL {url} - identified as HTML")
                                continue
                                
                            with open(path, "wb") as f:
                                f.write(resp.content)
                            
                            logger.info(f"Successfully downloaded URL to {path}")
                        
                        local_media_paths.append(path)
                        temp_files_to_cleanup.append(path)
                        
                    except Exception as dl_err:
                        logger.error(f"Failed to process media: {dl_err}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in media processing block: {e}", exc_info=True)

    # =========================================================================
    # PUBLISHING LOOP
    # =========================================================================
    for target in accounts:
        platform = target.get('platform')
        account_id = target.get('accountId') or target.get('account_id') # Support both naming

        # Find the linked account in user model
        account = next((a for a in user.linked_accounts if a.platform == platform and a.account_id == account_id), None)
        
        if not account:
            results.append({"platform": platform, "status": "failed", "error": "Account not linked"})
            continue
            
        try:
            token = decrypt_token(account.access_token_enc)
            
            # --- TWITTER ---
            if platform == "twitter":
                # Check expiry
                if account.expires_at and account.expires_at < datetime.datetime.utcnow():
                    if account.refresh_token_enc:
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
                        except Exception as refresh_error:
                            results.append({"platform": "twitter", "status": "failed", "error": f"Token refresh failed: {refresh_error}"})
                            continue
                    else:
                        results.append({"platform": "twitter", "status": "failed", "error": "Token expired, no refresh token"})
                        continue
                
                # Upload Media
                media_ids = []
                if local_media_paths:
                    for path in local_media_paths:
                        media_id = await twitter.upload_media(
                            token, file_path=path,
                            api_key=os.getenv("TWITTER_API_KEY"),
                            api_secret=os.getenv("TWITTER_API_SECRET"),
                            access_token_oauth1=os.getenv("TWITTER_ACCESS_TOKEN"),
                            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
                        )
                        media_ids.append(media_id)
                
                res = await twitter.post_tweet(token, content, media_ids=media_ids)
                results.append({"platform": "twitter", "status": "success", "id": res.get("data", {}).get("id")})
                
                # Log Activity
                await ActivityLog(
                    userId=str(user.id),
                    title="Posted to Twitter",
                    platform="Twitter",
                    type="success",
                    meta={"postId": res.get("data", {}).get("id")}
                ).insert()

            # --- INSTAGRAM ---
            elif platform == "instagram":
                if not media_urls:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media URL required"})
                    continue
                
                if is_video:
                    res = await instagram.publish_video(token, account_id, media_urls[0], content)
                else:
                    res = await instagram.publish_image(token, account_id, media_urls[0], content)
                
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Instagram", platform="Instagram", type="success").insert()

            # --- FACEBOOK ---
            elif platform == "facebook":
                if media_urls:
                    if is_video:
                         res = await facebook.post_video(token, account_id, content, media_urls[0])
                    else:
                         res = await facebook.post_photo(token, account_id, content, media_urls[0])
                else:
                    res = await facebook.post_to_page(token, account_id, content)
                
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Facebook", platform="Facebook", type="success").insert()

            # --- LINKEDIN ---
            elif platform == "linkedin":
                if media_urls:
                    media_type_str = "video" if is_video else "image"
                    reg_res = await linkedin.register_upload(token, account_id, media_type=media_type_str)
                    upload_url = reg_res['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                    asset_urn = reg_res['value']['asset']
                    
                    image_data = None
                    if local_media_paths:
                        with open(local_media_paths[0], "rb") as f:
                            image_data = f.read()
                    elif media_urls:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(media_urls[0])
                            image_data = resp.content
                            
                    if image_data:
                        await linkedin.upload_asset(upload_url, image_data, token)
                        res = await linkedin.post_with_media(token, account_id, content, asset_urn, media_type=media_type_str)
                    else:
                        res = await linkedin.post_to_profile(token, account_id, content)
                else:
                    res = await linkedin.post_to_profile(token, account_id, content)
                
                results.append({"platform": "linkedin", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to LinkedIn", platform="LinkedIn", type="success").insert()
            
            # --- TIKTOK ---
            elif platform == "tiktok":
                if not is_video or not media_urls:
                    results.append({"platform": "tiktok", "status": "failed", "error": "TikTok requires a video file."})
                    continue
                    
                # TikTok Post
                # We need the direct URL for the module to read (since our module reads URL using httpx)
                # Ensure media_urls[0] is accessible or logic in tiktok.py handles it
                res = await tiktok.post_video(token, account_id, media_urls[0], content)
                
                results.append({"platform": "tiktok", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to TikTok", platform="TikTok", type="success").insert()

            else:
                results.append({"platform": platform, "status": "failed", "error": "Not implemented"})

        except Exception as e:
            logger.error(f"Failed to post to {platform}: {e}", exc_info=True)
            results.append({"platform": platform, "status": "failed", "error": str(e)})
            await ActivityLog(
                userId=str(user.id), 
                title=f"Failed to post to {platform}", 
                platform=platform, 
                type="error", 
                meta={"error": str(e)}
            ).insert()

    # Cleanup temporary files
    for path in temp_files_to_cleanup:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    return {"results": results}
