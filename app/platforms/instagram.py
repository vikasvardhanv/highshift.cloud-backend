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

async def publish_image(access_token: str, ig_user_id: str, image_url: str, caption: str):
    async with httpx.AsyncClient() as client:
        # 1. Create container
        # Supported params: https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
        create_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": access_token
            }
        )
        create_res.raise_for_status()
        container_id = create_res.json().get("id")

        # 2. Publish container
        pub_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token
            }
        )
        pub_res.raise_for_status()
        return pub_res.json()

async def publish_video(access_token: str, ig_user_id: str, video_url: str, caption: str):
    """
    Publish a video to Instagram (Reels/Feed).
    Note: video_url must be public and accessible by Facebook servers.
    """
    async with httpx.AsyncClient() as client:
        # 1. Create container with media_type=VIDEO
        create_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            params={
                "media_type": "VIDEO",
                "video_url": video_url,
                "caption": caption,
                "access_token": access_token
            }
        )
        create_res.raise_for_status()
        container_id = create_res.json().get("id")

        # 2. Check status (Video upload is async on IG side)
        # We need to wait until status_code is FINISHED
        import asyncio
        max_retries = 10
        for _ in range(max_retries):
            status_res = await client.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": access_token
                }
            )
            status_data = status_res.json()
            if status_data.get("status_code") == "FINISHED":
                break
            if status_data.get("status_code") == "ERROR":
                 raise Exception(f"Instagram Video Processing Failed: {status_data}")
            await asyncio.sleep(2) # Poll every 2s
            
        # 3. Publish container
        pub_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token
            }
        )
        pub_res.raise_for_status()
        return pub_res.json()

async def get_me(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v19.0/me",
            params={
                "fields": "id,name,username,account_type,media_count",
                "access_token": access_token
            }
        )
        res.raise_for_status()
        return res.json()
