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
from app.models.media import Media
from app.services.token_service import decrypt_token, encrypt_token
from app.platforms import instagram, twitter, facebook, linkedin, tiktok, youtube, pinterest, threads, bluesky, mastodon

logger = logging.getLogger("publishing")

# Platform content requirements
PLATFORM_REQUIREMENTS = {
    "twitter": {
        "needs_content_or_media": True,
        "max_text_length": 280,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "Twitter requires either text (max 280 chars) or media (image/video)."
    },
    "instagram": {
        "needs_media": True,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "Instagram requires media (image or video). Text-only posts are not supported."
    },
    "facebook": {
        "needs_content_or_media": True,
        "max_text_length": 63206,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "Facebook requires either text or media (image/video)."
    },
    "tiktok": {
        "needs_video": True,
        "supports_videos": True,
        "error_msg": "TikTok only supports video content. Please upload a video."
    },
    "youtube": {
        "needs_video": True,
        "supports_videos": True,
        "error_msg": "YouTube only supports video content. Please upload a video."
    },
    "linkedin": {
        "needs_content_or_media": True,
        "max_text_length": 3000,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "LinkedIn requires either text (max 3000 chars) or media."
    },
    "pinterest": {
        "needs_media": True,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "Pinterest requires an image or video."
    },
    "threads": {
        "needs_content_or_media": True,
        "max_text_length": 500,
        "supports_images": True,
        "error_msg": "Threads requires either text (max 500 chars) or an image."
    },
    "bluesky": {
        "needs_content_or_media": True,
        "max_text_length": 300,
        "supports_images": True,
        "error_msg": "Bluesky requires either text (max 300 chars) or images."
    },
    "mastodon": {
        "needs_content_or_media": True,
        "max_text_length": 500,
        "supports_images": True,
        "supports_videos": True,
        "error_msg": "Mastodon requires either text (max 500 chars) or media."
    }
}

def validate_platform_content(platform: str, content: str, has_media: bool, is_video: bool) -> Optional[str]:
    """Validate content meets platform requirements. Returns error message or None if valid."""
    reqs = PLATFORM_REQUIREMENTS.get(platform, {})
    
    has_text = bool(content and content.strip())
    
    # Check if video is required
    if reqs.get("needs_video") and (not has_media or not is_video):
        return reqs.get("error_msg", f"{platform} requires a video.")
    
    # Check if media is required
    if reqs.get("needs_media") and not has_media:
        return reqs.get("error_msg", f"{platform} requires media.")
    
    # Check if content or media is required
    if reqs.get("needs_content_or_media") and not has_text and not has_media:
        return reqs.get("error_msg", f"{platform} requires either text or media.")
    
    # Check text length
    max_len = reqs.get("max_text_length")
    if max_len and has_text and len(content) > max_len:
        return f"{platform.capitalize()} text exceeds {max_len} character limit ({len(content)} chars)."
    
    return None

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
    temp_files_to_cleanup = []
    
    # Determine media types for all media
    media_items = [] # List of {url: str, path: str, is_video: bool}
    
    # If media_urls contain data:image/base64 strings, we must save them to files
    processed_media_urls = []
    processed_local_paths = list(local_media_paths) if local_media_paths else []

    # Track video status alongside URLs
    processed_media_types = []  # Parallel list: True if video, False if image
    
    for url in media_urls:
        if url.startswith("data:"):
            try:
                # Extract mime type and base64 data
                header, encoded = url.split(",", 1)
                mime = header.split(";", 1)[0].split(":")[1]
                ext = mimetypes.guess_extension(mime) or ".jpg"
                is_vid = "video" in mime
                
                # Save to temporary file (for platforms like Facebook that support direct upload)
                fd, path = tempfile.mkstemp(suffix=ext)
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(base64.b64decode(encoded))
                
                processed_local_paths.append(path)
                temp_files_to_cleanup.append(path)
                
                # Also save to MongoDB for public URL (needed by Instagram, TikTok)
                media_doc = Media(
                    user_id=str(user.id),
                    filename=f"upload{ext}",
                    content_type=mime,
                    file_type="video" if is_vid else "image",
                    data_url=url,
                    size_bytes=len(base64.b64decode(encoded))
                )
                await media_doc.insert()
                public_url = media_doc.get_public_url()
                processed_media_urls.append(public_url)
                processed_media_types.append(is_vid)
                logger.info(f"Saved base64 media to MongoDB: {media_doc.media_id} -> {public_url} (video={is_vid})")
                
            except Exception as e:
                logger.error(f"Failed to process base64 media: {e}")
                processed_media_urls.append(None)
                processed_media_types.append(False)
        elif url.startswith("blob:"):
            return {"results": [{"platform": "all", "status": "failed", "error": "Media is still uploading or invalid (blob URL). Please wait a moment and try again."}]}
        else:
            processed_media_urls.append(url)
            # Check extension for non-base64 URLs
            ext = url.split('?')[0].split('.')[-1].lower()
            processed_media_types.append(ext in ['mp4', 'mov', 'avi', 'mkv', 'webm'])

    # Re-align media items based on processed inputs
    for i in range(max(len(processed_media_urls), len(processed_local_paths))):
        u = processed_media_urls[i] if i < len(processed_media_urls) else None
        p = processed_local_paths[i] if i < len(processed_local_paths) else None
        
        # Check if video - use tracked type if available, otherwise guess from path/url
        is_v = False
        if i < len(processed_media_types):
            is_v = processed_media_types[i]
        elif p:
            mime, _ = mimetypes.guess_type(p)
            if mime and "video" in mime: is_v = True
        elif u:
            ext = u.split('?')[0].split('.')[-1].lower()
            if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']: is_v = True
        
        media_items.append({"url": u, "path": p, "is_video": is_v})

    is_video = any(item["is_video"] for item in media_items)
    logger.info(f"Publishing Content (User {user.id}): Items={len(media_items)}, AnyVideo={is_video}")

    # Extract first link from content for platforms that support it (if no media)
    link_in_text = None
    if content:
        urls = re.findall(r'(https?://[^\s]+)', content)
        if urls: link_in_text = urls[0]

    # =========================================================================
    # PUBLISHING LOOP
    # =========================================================================
    for target in accounts:
        platform = target.get('platform')
        account_id = target.get('accountId') or target.get('account_id')

        account = next((a for a in user.linked_accounts if a.platform == platform and a.account_id == account_id), None)
        if not account:
            results.append({"platform": platform, "status": "failed", "error": "Account not linked"})
            continue
            
        try:
            token = decrypt_token(account.access_token_enc)
            
            # Validate content meets platform requirements
            has_media = bool(media_items)
            validation_error = validate_platform_content(platform, content, has_media, is_video)
            if validation_error:
                results.append({"platform": platform, "status": "failed", "error": validation_error})
                continue
            
            
            # --- TWITTER ---
            if platform == "twitter":
                # Check expiry and refresh if needed
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
                            logger.error(f"Twitter token refresh failed: {refresh_error}")
                            results.append({
                                "platform": "twitter", 
                                "status": "failed", 
                                "error": "Your Twitter session has expired. Please reconnect Twitter from your dashboard.",
                                "action_required": "reconnect"
                            })
                            continue
                    else:
                        results.append({
                            "platform": "twitter", 
                            "status": "failed", 
                            "error": "Your Twitter session has expired. Please reconnect Twitter from your dashboard.",
                            "action_required": "reconnect"
                        })
                        continue

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
                await ActivityLog(userId=str(user.id), title="Posted to Twitter", platform="Twitter", type="success").insert()

            # --- INSTAGRAM ---
            elif platform == "instagram":
                if not media_items:
                    results.append({"platform": "instagram", "status": "failed", "error": "Media required for Instagram"})
                    continue
                
                # Check for public URLs (Instagram requirement)
                # With MongoDB storage, we now have public URLs for base64 uploads
                if not any(item["url"] for item in media_items):
                    results.append({"platform": "instagram", "status": "failed", "error": "No public URL available for media. Please try uploading again."})
                    continue


                if len(media_items) > 1:
                    res = await instagram.publish_carousel(token, account_id, media_items, content)
                elif is_video:
                    res = await instagram.publish_video(token, account_id, media_items[0]["url"], content, local_path=media_items[0]["path"])
                else:
                    res = await instagram.publish_image(token, account_id, media_items[0]["url"], content, local_path=media_items[0]["path"])
                
                results.append({"platform": "instagram", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Instagram", platform="Instagram", type="success").insert()

            # --- FACEBOOK ---
            elif platform == "facebook":
                if is_video:
                    res = await facebook.post_video(
                        token, account_id, content, 
                        media_items[0]["url"], 
                        local_path=media_items[0]["path"]
                    )
                elif media_items:
                    res = await facebook.post_photo(
                        token, account_id, content, 
                        [m["url"] for m in media_items],
                        local_paths=[m["path"] for m in media_items]
                    )
                elif link_in_text:
                    res = await facebook.post_to_page(token, account_id, content, link=link_in_text)
                else:
                    res = await facebook.post_to_page(token, account_id, content)
                
                results.append({"platform": "facebook", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Facebook", platform="Facebook", type="success").insert()

            # --- LINKEDIN ---
            elif platform == "linkedin":
                if media_items:
                    media_type_str = "video" if is_video else "image"
                    asset_urns = []
                    
                    for item in media_items:
                        reg_res = await linkedin.register_upload(token, account_id, media_type=media_type_str)
                        upload_url = reg_res['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
                        asset_urn = reg_res['value']['asset']
                        
                        image_data = None
                        if item["path"]:
                            with open(item["path"], "rb") as f: image_data = f.read()
                        elif item["url"]:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(item["url"])
                                image_data = resp.content
                        
                        if image_data:
                            await linkedin.upload_asset(upload_url, image_data, token)
                            asset_urns.append(asset_urn)
                    
                    if asset_urns:
                        res = await linkedin.post_with_media(token, account_id, content, asset_urns, media_type=media_type_str)
                    else:
                        res = await linkedin.post_to_profile(token, account_id, content)
                else:
                    res = await linkedin.post_to_profile(token, account_id, content)
                
                results.append({"platform": "linkedin", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to LinkedIn", platform="LinkedIn", type="success").insert()
            
            # --- TIKTOK ---
            elif platform == "tiktok":
                if not is_video or not media_items:
                    results.append({"platform": "tiktok", "status": "failed", "error": "TikTok requires a video."})
                    continue
                # Use the processed URL (MongoDB public URL) not the raw base64
                video_url = media_items[0]["url"]
                if not video_url or video_url.startswith("data:"):
                    results.append({"platform": "tiktok", "status": "failed", "error": "TikTok requires a public video URL, not base64 data."})
                    continue
                res = await tiktok.post_video(token, account_id, video_url, content)
                results.append({"platform": "tiktok", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to TikTok", platform="TikTok", type="success").insert()

            # --- YOUTUBE ---
            elif platform == "youtube":
                if not is_video or not local_media_paths:
                    results.append({"platform": "youtube", "status": "failed", "error": "YouTube requires a local video file."})
                    continue
                res = await youtube.upload_video(token, local_media_paths[0], content[:100], content)
                results.append({"platform": "youtube", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to YouTube", platform="YouTube", type="success").insert()

            # --- PINTEREST ---
            elif platform == "pinterest":
                if not media_urls:
                     results.append({"platform": "pinterest", "status": "failed", "error": "Pinterest requires an image."})
                     continue
                
                board_id = account_id
                boards = await pinterest.get_boards(token)
                if boards: board_id = boards[0]['id']
                
                res = await pinterest.create_pin(token, board_id, content[:100], content, link=link_in_text, media_url=media_urls[0])
                results.append({"platform": "pinterest", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Pinterest", platform="Pinterest", type="success").insert()

            # --- THREADS ---
            elif platform == "threads":
                res = await threads.post_thread(token, account_id, content, media_urls=media_items)
                results.append({"platform": "threads", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Threads", platform="Threads", type="success").insert()

            # --- MASTODON ---
            elif platform == "mastodon":
                instance_url = account.raw_profile.get("_instance_url")
                if not instance_url and "@" in account.username:
                    parts = account.username.split("@")
                    if len(parts) == 2: instance_url = "https://" + parts[1]
                
                if not instance_url:
                     results.append({"platform": "mastodon", "status": "failed", "error": "Instance URL not found."})
                     continue
                
                media_ids = []
                if local_media_paths:
                    for path in local_media_paths:
                        m_res = await mastodon.upload_media(instance_url, token, path)
                        media_ids.append(m_res.get("id"))
                
                res = await mastodon.post_status(instance_url, token, content, media_ids)
                results.append({"platform": "mastodon", "status": "success", "id": res.get("id")})
                await ActivityLog(userId=str(user.id), title="Posted to Mastodon", platform="Mastodon", type="success").insert()

            # --- BLUESKY ---
            elif platform == "bluesky":
                embed = None
                if local_media_paths:
                    images = []
                    for path in local_media_paths[:len(local_media_paths)]:
                        with open(path, "rb") as f:
                            img_data = f.read()
                            blob = await bluesky.upload_blob(token, img_data)
                            images.append({"image": blob, "alt": content[:100] if content else ""})
                    if images:
                        embed = {"$type": "app.bsky.embed.images", "images": images}
                
                res = await bluesky.create_record(token, account_id, content, embed=embed)
                results.append({"platform": "bluesky", "status": "success", "id": res.get("uri")})
                await ActivityLog(userId=str(user.id), title="Posted to Bluesky", platform="Bluesky", type="success").insert()

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
