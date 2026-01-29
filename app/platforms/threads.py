import httpx
from app.utils.logger import logger
import urllib.parse
import os

# Threads API (Graph API based)
# Uses the same Facebook/Meta App setup but different endpoints/scopes.
GRAPH_API_BASE = "https://graph.threads.net/v1.0"

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(scopes),
        "response_type": "code",
        "state": state
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"https://threads.net/oauth/authorize?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{GRAPH_API_BASE}/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code
            }
        )
        res.raise_for_status()
        return res.json()

async def get_user_info(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{GRAPH_API_BASE}/me",
            params={
                "fields": "id,username,name,threads_profile_picture_url,threads_biography",
                "access_token": access_token
            }
        )
        res.raise_for_status()
        return res.json()

async def post_thread(access_token: str, user_id: str, text: str, media_urls: list = None):
    """
    Publish a Thread. Supports multiple items (Carousel).
    media_urls: List of dicts with {url, is_video}
    """
    async with httpx.AsyncClient() as client:
        if not media_urls:
            # Text-only post
            res = await client.post(
                f"{GRAPH_API_BASE}/{user_id}/threads",
                params={"access_token": access_token,"text": text,"media_type": "TEXT"}
            )
            res.raise_for_status()
            container_id = res.json().get("id")
        elif len(media_urls) == 1:
            # Single item post
            item = media_urls[0]
            params = {"access_token": access_token, "text": text}
            if item.get("is_video"):
                params["media_type"] = "VIDEO"
                params["video_url"] = item["url"]
            else:
                params["media_type"] = "IMAGE"
                params["image_url"] = item["url"]
            
            res = await client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
            res.raise_for_status()
            container_id = res.json().get("id")
        else:
            # Multi-item (Carousel)
            item_ids = []
            for item in media_urls:
                params = {"access_token": access_token, "is_carousel_item": "true"}
                if item.get("is_video"):
                    params["media_type"] = "VIDEO"
                    params["video_url"] = item["url"]
                else:
                    params["media_type"] = "IMAGE"
                    params["image_url"] = item["url"]
                
                res = await client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
                res.raise_for_status()
                item_ids.append(res.json().get("id"))
            
            # Wait for items to process
            import asyncio
            for c_id in item_ids:
                for _ in range(20):
                    s_res = await client.get(f"{GRAPH_API_BASE}/{c_id}", params={"fields": "status", "access_token": access_token})
                    if s_res.json().get("status") == "FINISHED": break
                    await asyncio.sleep(3)
            
            # Carousel Container
            res = await client.post(
                f"{GRAPH_API_BASE}/{user_id}/threads",
                params={
                    "media_type": "CAROUSEL",
                    "children": ",".join(item_ids),
                    "text": text,
                    "access_token": access_token
                }
            )
            res.raise_for_status()
            container_id = res.json().get("id")

        # Polling for processing completion before publishing
        import asyncio
        for _ in range(30):
            status_res = await client.get(
                f"{GRAPH_API_BASE}/{container_id}",
                params={"fields": "status", "access_token": access_token}
            )
            if status_res.json().get("status") == "FINISHED":
                break
            await asyncio.sleep(5)
            
        # Step 2: Publish Container
        publish_res = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token
            }
        )
        publish_res.raise_for_status()
        return publish_res.json()
