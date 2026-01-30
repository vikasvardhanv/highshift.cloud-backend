import httpx
import os
from app.utils.logger import logger

def _extract_fb_error(res):
    """Extract error message from Facebook Graph API response."""
    try:
        data = res.json()
        error = data.get("error", {})
        return error.get("message", str(data))
    except:
        return f"HTTP {res.status_code}"

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(scopes)
    }
    return f"https://www.facebook.com/v19.0/dialog/oauth?{'&'.join([f'{k}={v}' for k,v in params.items()])}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code
            }
        )
        if res.status_code != 200:
            raise Exception(f"Facebook token exchange failed: {_extract_fb_error(res)}")
        return res.json()

async def post_to_page(access_token: str, page_id: str, message: str, link: str = None):
    async with httpx.AsyncClient() as client:
        params = {
            "message": message,
            "access_token": access_token
        }
        if link:
            params["link"] = link
            
        res = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed",
            params=params
        )
        if res.status_code != 200:
            raise Exception(f"Facebook post failed: {_extract_fb_error(res)}")
        return res.json()

async def post_photo(access_token: str, page_id: str, message: str, image_urls: list, local_paths: list = None):
    """
    Post one or more photos to a Facebook Page.
    Supports both public URLs and local file paths.
    """
    async with httpx.AsyncClient() as client:
        # Normalize local_paths to match image_urls length
        paths = local_paths or [None] * len(image_urls)
        
        if len(image_urls) == 1:
            # Single photo post
            files = None
            params = {"access_token": access_token, "caption": message}
            
            if paths[0] and os.path.exists(paths[0]):
                files = {"source": open(paths[0], "rb")}
            else:
                params["url"] = image_urls[0]
            
            res = await client.post(
                f"https://graph.facebook.com/v19.0/{page_id}/photos", 
                params=params, 
                files=files
            )
        else:
            # Multi-photo post
            media_fbid_list = []
            for i, url in enumerate(image_urls):
                p = paths[i] if i < len(paths) else None
                data = {"published": "false", "access_token": access_token}
                files = None
                params = {}
                
                if p and os.path.exists(p):
                    files = {"source": open(p, "rb")}
                else:
                    params["url"] = url
                    
                upload_res = await client.post(
                    f"https://graph.facebook.com/v19.0/{page_id}/photos", 
                    params=params if not files else {"access_token": access_token, "published": "false"}, 
                    files=files
                )
                if upload_res.status_code != 200:
                    raise Exception(f"Facebook photo upload failed: {_extract_fb_error(upload_res)}")
                media_fbid_list.append(upload_res.json().get("id"))
            
            # 2. Create feed post with attached_media
            attached_media = [{"media_fbid": fbid} for fbid in media_fbid_list]
            import json
            params = {
                "message": message,
                "attached_media": json.dumps(attached_media),
                "access_token": access_token
            }
            res = await client.post(f"https://graph.facebook.com/v19.0/{page_id}/feed", params=params)
            
        if res.status_code != 200:
            raise Exception(f"Facebook photo post failed: {_extract_fb_error(res)}")
        return res.json()

async def post_video(access_token: str, page_id: str, message: str, video_url: str, local_path: str = None):
    """
    Post a video to a Facebook Page.
    Supports both public URL (file_url) and local file (source).
    """
    async with httpx.AsyncClient() as client:
        data = {"description": message, "access_token": access_token}
        files = None
        params = {}
        
        if local_path and os.path.exists(local_path):
            # For videos, Facebook prefers the 'source' parameter in a multipart form
            files = {"source": open(local_path, "rb")}
        else:
            params["file_url"] = video_url
        
        # Facebook Video API: https://graph.facebook.com/{page-id}/videos
        res = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/videos",
            params=params if not files else {"access_token": access_token, "description": message},
            files=files
        )
        if res.status_code != 200:
            raise Exception(f"Facebook video post failed: {_extract_fb_error(res)}")
        return res.json()

async def get_me(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v19.0/me",
            params={
                "fields": "id,name,email",
                "access_token": access_token
            }
        )
        if res.status_code != 200:
            raise Exception(f"Facebook get_me failed: {_extract_fb_error(res)}")
        return res.json()

async def get_accounts(access_token: str):
    """
    Fetch Facebook Pages and linked Instagram Business Accounts.
    """
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={
                    "fields": "id,name,access_token,picture,instagram_business_account{id,name,username,profile_picture_url},tasks", 
                    "limit": "100",
                    "access_token": access_token
                }
            )
            
            logger.info(f"Facebook API Response Status: {res.status_code}")
            if res.status_code != 200:
                raise Exception(f"Facebook get_accounts failed: {_extract_fb_error(res)}")
            data = res.json()
            
            all_pages = data.get("data", [])
            
            # Pagination
            next_page = data.get("paging", {}).get("next")
            while next_page:
                try:
                    logger.info("Fetching next page of Facebook Accounts...")
                    res = await client.get(next_page)
                    if res.status_code != 200:
                        logger.error(f"Facebook pagination error: {_extract_fb_error(res)}")
                        break
                    data = res.json()
                    all_pages.extend(data.get("data", []))
                    next_page = data.get("paging", {}).get("next")
                except Exception as e:
                    logger.error(f"Error fetching next page: {e}")
                    break

            logger.info(f"Facebook Pages Found: {len(all_pages)} pages")
            
            return all_pages
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_accounts: {str(e)}")
            raise


async def get_permissions(access_token: str):
    """
    Fetch granted permissions to debug scope issues.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v19.0/me/permissions",
            params={"access_token": access_token}
        )
        if res.status_code != 200:
            return []
        data = res.json()
        return data.get("data", [])

