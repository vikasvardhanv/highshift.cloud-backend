import httpx
from app.utils.logger import logger

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
        res.raise_for_status()
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
        res.raise_for_status()
        return res.json()

async def post_photo(access_token: str, page_id: str, message: str, image_url: str):
    """
    Post a photo to a Facebook Page using an image URL.
    """
    async with httpx.AsyncClient() as client:
        params = {
            "url": image_url,
            "caption": message,
            "access_token": access_token
        }
        
        res = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/photos",
            params=params
        )
        res.raise_for_status()
        return res.json()

async def post_video(access_token: str, page_id: str, message: str, video_url: str):
    """
    Post a video to a Facebook Page using a video URL.
    """
    async with httpx.AsyncClient() as client:
        params = {
            "file_url": video_url,
            "description": message,
            "access_token": access_token
        }
        
        # Facebook Video API: https://graph.facebook.com/{page-id}/videos
        res = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/videos",
            params=params
        )
        res.raise_for_status()
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
        res.raise_for_status()
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
                    "fields": "id,name,access_token,picture,instagram_business_account,tasks", 
                    "limit": "100",
                    "access_token": access_token
                }
            )
            
            logger.info(f"Facebook API Response Status: {res.status_code}")
            res.raise_for_status()
            data = res.json()
            
            all_pages = data.get("data", [])
            
            # Pagination
            next_page = data.get("paging", {}).get("next")
            while next_page:
                try:
                    logger.info("Fetching next page of Facebook Accounts...")
                    res = await client.get(next_page)
                    res.raise_for_status()
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
