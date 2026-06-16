import httpx
import os
from urllib.parse import urlencode
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
        "scope": ",".join(scopes),
        # Always re-show the page-selection dialog so the user can pick pages.
        # Without this, Facebook skips the page selector if previously authorized.
        "auth_type": "rerequest",
    }
    return f"https://www.facebook.com/v21.0/dialog/oauth?{urlencode(params)}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v21.0/oauth/access_token",
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

async def exchange_long_lived_token(client_id: str, client_secret: str, user_access_token: str) -> str:
    """Exchange a short-lived user access token for a long-lived user access token."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v21.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "fb_exchange_token": user_access_token
            }
        )
        if res.status_code != 200:
            raise Exception(f"Facebook long-lived token exchange failed: {_extract_fb_error(res)}")
        return res.json().get("access_token")

async def post_to_page(access_token: str, page_id: str, message: str, link: str = None):
    async with httpx.AsyncClient() as client:
        params = {
            "message": message,
            "access_token": access_token
        }
        if link:
            params["link"] = link
            
        res = await client.post(
            f"https://graph.facebook.com/v21.0/{page_id}/feed",
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
                f"https://graph.facebook.com/v21.0/{page_id}/photos", 
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
                    f"https://graph.facebook.com/v21.0/{page_id}/photos", 
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
            res = await client.post(f"https://graph.facebook.com/v21.0/{page_id}/feed", params=params)
            
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
            f"https://graph.facebook.com/v21.0/{page_id}/videos",
            params=params if not files else {"access_token": access_token, "description": message},
            files=files
        )
        if res.status_code != 200:
            raise Exception(f"Facebook video post failed: {_extract_fb_error(res)}")
        return res.json()

async def get_me(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v21.0/me",
            params={
                "fields": "id,name,email",
                "access_token": access_token
            }
        )
        if res.status_code != 200:
            raise Exception(f"Facebook get_me failed: {_extract_fb_error(res)}")
        return res.json()

async def get_page_access_token(user_access_token: str, page_id: str) -> str | None:
    """Fetch a fresh Page access token using a long-lived user access token."""
    pages = await get_accounts(user_access_token)
    for page in pages:
        if str(page.get("id")) == str(page_id):
            return page.get("access_token")
    return None


async def get_accounts(access_token: str):
    """
    Fetch Facebook Pages and linked Instagram Business Accounts.
    Tries /me/accounts first, then falls back to the Business Manager API
    for pages managed via Meta Business Suite.
    """
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                "https://graph.facebook.com/v21.0/me/accounts",
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

            logger.info(f"Facebook Pages Found via /me/accounts: {len(all_pages)} pages")

            # --- Business API fallback ---
            # /me/accounts returns empty for pages managed through Meta Business Suite.
            # When that happens, try fetching pages via the Business Manager API.
            if not all_pages:
                logger.info("No pages via /me/accounts — trying Business API fallback")
                all_pages = await _get_accounts_via_business(client, access_token)

            return all_pages
        except httpx.HTTPStatusError as e:
            logger.error(f"Facebook API Error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_accounts: {str(e)}")
            raise


async def _get_accounts_via_business(client: httpx.AsyncClient, access_token: str) -> list:
    """
    Fallback: fetch pages through the Business Manager API.
    Works for pages managed via Meta Business Suite where /me/accounts returns empty.
    Requires the business_management permission.
    """
    page_fields = "id,name,access_token,picture,instagram_business_account{id,name,username,profile_picture_url},tasks"
    try:
        biz_res = await client.get(
            "https://graph.facebook.com/v21.0/me/businesses",
            params={
                "fields": f"id,name,owned_pages{{{page_fields}}},client_pages{{{page_fields}}}",
                "access_token": access_token,
                "limit": "50",
            }
        )
        if biz_res.status_code != 200:
            logger.warning(f"Business API fallback failed: {_extract_fb_error(biz_res)}")
            return []

        biz_data = biz_res.json().get("data", [])
        logger.info(f"Business API returned {len(biz_data)} businesses")

        pages = []
        seen_ids: set = set()
        for biz in biz_data:
            for key in ("owned_pages", "client_pages"):
                for page in (biz.get(key) or {}).get("data", []):
                    if page.get("id") not in seen_ids:
                        seen_ids.add(page["id"])
                        pages.append(page)

        logger.info(f"Business API fallback found {len(pages)} pages")
        return pages
    except Exception as e:
        logger.error(f"Business API fallback error: {e}")
        return []


async def get_permissions(access_token: str):
    """
    Fetch granted permissions to debug scope issues.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v21.0/me/permissions",
            params={"access_token": access_token}
        )
        if res.status_code != 200:
            return []
        data = res.json()
        return data.get("data", [])

