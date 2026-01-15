import httpx
import urllib.parse
import os
import json
from app.utils.logger import logger

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )
        res.raise_for_status()
        return res.json()

async def get_me(access_token: str):
    """
    Fetch the YouTube channel information for the authenticated user.
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "snippet,contentDetails,statistics",
                "mine": "true"
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        res.raise_for_status()
        data = res.json()
        
        items = data.get("items", [])
        if not items:
            return None
            
        channel = items[0]
        snippet = channel.get("snippet", {})
        
        return {
            "id": channel["id"],
            "name": snippet.get("title"),
            "picture": snippet.get("thumbnails", {}).get("default", {}).get("url"),
            "raw": channel
        }

async def upload_video(access_token: str, file_path: str, title: str, description: str, privacy_status: str = "public"):
    """
    Upload a video to YouTube using the Data API v3 resumable upload.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found at {file_path}")

    async with httpx.AsyncClient() as client:
        # Step 1: Initiate Resumable Upload
        metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": "22" # People & Blogs default
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }
        
        init_res = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(os.path.getsize(file_path))
            },
            json=metadata
        )
        
        if init_res.status_code != 200:
            logger.error(f"YouTube upload initialization failed: {init_res.text}")
            init_res.raise_for_status()
            
        upload_url = init_res.headers.get("Location")
        if not upload_url:
            raise Exception("Failed to get YouTube upload session URL")

        # Step 2: Upload the actual video file
        with open(file_path, "rb") as f:
            video_data = f.read()
            
        final_res = await client.put(
            upload_url,
            content=video_data,
            headers={
                "Content-Type": "video/*"
            },
            timeout=300.0 # Large videos need time
        )
        
        if final_res.status_code not in [200, 201]:
            logger.error(f"YouTube video bytes upload failed: {final_res.text}")
            final_res.raise_for_status()
            
        return final_res.json()
