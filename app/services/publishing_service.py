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
from app.platforms import instagram, twitter, facebook, linkedin, tiktok, youtube, pinterest, threads, bluesky, mastodon

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
    temp_files_to_cleanup = []
    
    # Determine media types for all media
    media_items = [] # List of {url: str, path: str, is_video: bool}
    
    # If media_urls contain data:image/base64 strings, we must save them to files
    processed_media_urls = []
    processed_local_paths = list(local_media_paths) if local_media_paths else []

    for url in media_urls:
        if url.startswith("data:"):
            try:
                # Extract mime type and base64 data
                header, encoded = url.split(",", 1)
                mime = header.split(";", 1)[0].split(":", 1)[1]
                ext = mimetypes.guess_extension(mime) or ".jpg"
                
                # Save to temporary file
                fd, path = tempfile.mkstemp(suffix=ext)
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(base64.b64decode(encoded))
                
                processed_local_paths.append(path)
                temp_files_to_cleanup.append(path)
                processed_media_urls.append(None) # Can't use base64 as URL for most APIs
                logger.info(f"Decoded base64 media to {path}")
            except Exception as e:
                logger.error(f"Failed to decode base64 media: {e}")
                processed_media_urls.append(url) # Fallback (will likely fail later but safe)
        elif url.startswith("blob:"):
            return [{"platform": "all", "status": "failed", "error": "Media is still uploading or invalid (blob URL). Please wait a moment and try again."}]
        else:
            processed_media_urls.append(url)

    # Re-align media items based on processed inputs
    for i in range(max(len(processed_media_urls), len(processed_local_paths))):
        u = processed_media_urls[i] if i < len(processed_media_urls) else None
        p = processed_local_paths[i] if i < len(processed_local_paths) else None
        
        # Check if video
        is_v = False
        target_v = p or u
        if target_v:
            if p:
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
                            results.append({"platform": "twitter", "status": "failed", "error": f"Token refresh failed: {refresh_error}"})
                            continue
                    else:
                        results.append({"platform": "twitter", "status": "failed", "error": "Token expired, no refresh token"})
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
                # If we have ONLY paths (common with base64 uploads from frontend), Instagram MUST fail
                if not any(item["url"] for item in media_items):
                    results.append({"platform": "instagram", "status": "failed", "error": "Instagram requires a PUBLICLY accessible URL. Base64/Direct uploads are not supported by Instagram's API directly; media must be hosted on a public server first."})
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
                if not is_video or not media_urls:
                    results.append({"platform": "tiktok", "status": "failed", "error": "TikTok requires a video."})
                    continue
                res = await tiktok.post_video(token, account_id, media_urls[0], content)
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
