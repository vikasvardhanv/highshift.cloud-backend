import httpx
from app.utils.logger import logger
import os

# TikTok API Endpoints (V2)
AUTH_URL_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

async def get_auth_url(client_key: str, redirect_uri: str, state: str, scopes: list):
    """
    Generates the TikTok OAuth authorization URL.
    """
    params = {
        "client_key": client_key,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(scopes)
    }
    # Note: TikTok might require 'scope' to be comma-separated or space-separated?
    # Docs say comma-separated for v2.
    return f"{AUTH_URL_BASE}?{'&'.join([f'{k}={v}' for k,v in params.items()])}"

async def exchange_code(client_key: str, client_secret: str, redirect_uri: str, code: str):
    """
    Exchanges the authorization code for an access token.
    """
    async with httpx.AsyncClient() as client:
        # TikTok requires sending parameters as application/x-www-form-urlencoded
        data = {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
        res = await client.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        # Check for error in response body explicitly because TikTok sometimes returns 200 with error inside
        res_json = res.json()
        if "error" in res_json:
             raise Exception(f"TikTok Token Error: {res_json}")
             
        res.raise_for_status()
        return res_json

async def get_user_info(access_token: str):
    """
    Fetches the authenticated user's profile info.
    Required Scope: user.info.basic
    """
    async with httpx.AsyncClient() as client:
        res = await client.get(
            USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "open_id,union_id,avatar_url,display_name,username"}
        )
        res_json = res.json()
        if "error" in res_json and res_json["error"]["code"] != "ok":
             raise Exception(f"TikTok User Info Error: {res_json}")
             
        return res_json.get("data", {}).get("user", {})

async def post_video(access_token: str, open_id: str, video_url: str, caption: str):
    """
    Publishes a video to TikTok via Direct Post API.
    Flow:
    1. Init upload (get upload_url)
    2. Upload video binary (PUT)
    3. TikTok processes it automatically? Or is there a finalize step?
    
    Actually, V2 'Direct Post' (post/publish/video/init/) returns an upload_url.
    We upload the video there.
    Then we don't need to 'finalize' explicitly, but we might check status.
    
    Constraint: The 'video_url' provided here is likely on OUR server or S3.
    We must READ it and PUT it to TikTok. We cannot just pass the URL to TikTok.
    """
    
    # 1. Init Upload
    async with httpx.AsyncClient() as client:
        init_body = {
            "post_info": {
                "title": caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": 0, # We need size!
                "chunk_size": 0, 
                "total_chunk_count": 1
            }
        }
        
        # We need to fetch the video first to get its size and binary data
        # This is expensive for the backend but required if TikTok doesn't support 'PULL_FROM_URL' (which it usually doesn't for user uploads)
        video_res = await client.get(video_url)
        if video_res.status_code != 200:
             raise Exception(f"Could not download video from {video_url} to upload to TikTok")
        
        video_data = video_res.content
        video_size = len(video_data)
        
        # Update init body with real size
        init_body["source_info"]["video_size"] = video_size
        init_body["source_info"]["chunk_size"] = video_size
        
        logger.info(f"Initializing TikTok upload for size: {video_size} bytes")
        
        init_res = await client.post(
            VIDEO_INIT_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            },
            json=init_body
        )
        
        init_json = init_res.json()
        if "error" in init_json and init_json["error"]["code"] != "ok":
             raise Exception(f"TikTok Init Error: {init_json}")
             
        upload_url = init_json["data"]["upload_url"]
        publish_id = init_json["data"]["publish_id"]
        
        # 2. Upload Video
        # TikTok expects a PUT to the provided URL
        upload_res = await client.put(
            upload_url,
            content=video_data,
            headers={
                "Content-Type": "video/mp4", # Assuming MP4 for now
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size-1}/{video_size}"
            }
        )
        
        if upload_res.status_code not in [200, 201]:
             raise Exception(f"TikTok Video Upload Failed: {upload_res.status_code} {upload_res.text}")
             
        # 3. Done?
        # The 'Direct Post' API usually triggers processing after upload completes.
        return {"id": publish_id, "status": "published_pending_processing"}
