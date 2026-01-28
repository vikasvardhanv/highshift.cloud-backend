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

async def post_thread(access_token: str, user_id: str, text: str, media_url: str = None, media_type: str = "IMAGE"):
    """
    Publish a Thread. Two-step process: Create Container -> Publish Container.
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Create Container
        params = {
            "access_token": access_token,
            "media_type": media_type,
            "text": text
        }
        if media_url:
            if media_type == "IMAGE":
                params["image_url"] = media_url
            elif media_type == "VIDEO":
                params["video_url"] = media_url
        
        container_res = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads",
            params=params
        )
        container_res.raise_for_status()
        container_id = container_res.json().get("id")
        
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
