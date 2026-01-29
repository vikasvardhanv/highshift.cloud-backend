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

import os

async def publish_image(access_token: str, ig_user_id: str, image_url: str, caption: str, local_path: str = None):
    async with httpx.AsyncClient() as client:
        # 1. Create container
        params = {
            "caption": caption,
            "access_token": access_token
        }
        files = None
        if local_path and os.path.exists(local_path):
            files = {"image_url": open(local_path, "rb")}
        else:
            params["image_url"] = image_url

        res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            params=params if not files else {"access_token": access_token, "caption": caption},
            files=files
        )
        res.raise_for_status()
        container_id = res.json().get("id")

        # 2. Publish
        pub_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": access_token}
        )
        pub_res.raise_for_status()
        return pub_res.json()

async def publish_video(access_token: str, ig_user_id: str, video_url: str, caption: str, local_path: str = None):
    async with httpx.AsyncClient() as client:
        # 1. Create container
        params = {
            "media_type": "VIDEO",
            "caption": caption,
            "access_token": access_token
        }
        files = None
        if local_path and os.path.exists(local_path):
            # Instagram requires video to be uploaded as 'video_url' normally, 
            # but 'video_url' in multipart form is also supported for some endpoints.
            files = {"video_url": open(local_path, "rb")}
        else:
            params["video_url"] = video_url

        res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            params=params if not files else {"access_token": access_token, "media_type": "VIDEO", "caption": caption},
            files=files
        )
        res.raise_for_status()
        container_id = res.json().get("id")

        # 2. Poll
        import asyncio
        max_retries = 30
        for _ in range(max_retries):
            status_res = await client.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={"fields": "status_code", "access_token": access_token}
            )
            data = status_res.json()
            if data.get("status_code") == "FINISHED":
                break
            if data.get("status_code") == "ERROR":
                raise Exception(f"Instagram media processing failed: {data.get('status_msg', 'Unknown Error')}")
            await asyncio.sleep(5)

        # 3. Publish
        pub_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": access_token}
        )
        pub_res.raise_for_status()
        return pub_res.json()

async def publish_carousel(access_token: str, ig_user_id: str, media_urls: list, caption: str):
    """
    Publish a carousel (multi-item) post to Instagram.
    media_urls: List of dicts with {url, is_video}
    """
    async with httpx.AsyncClient() as client:
        # 1. Create individual item containers
        item_ids = []
        for item in media_urls:
            params = {
                "access_token": access_token,
                "is_carousel_item": "true",
                "caption": caption # Caption is technically ignored for carousel items but good to have
            }
            if item.get("is_video"):
                params["media_type"] = "VIDEO"
                params["video_url"] = item["url"]
            else:
                params["image_url"] = item["url"]
                
            res = await client.post(f"https://graph.facebook.com/v19.0/{ig_user_id}/media", params=params)
            res.raise_for_status()
            item_ids.append(res.json().get("id"))

        # 2. Wait for items to process (especially videos)
        import asyncio
        for container_id in item_ids:
            max_retries = 20
            for _ in range(max_retries):
                status_res = await client.get(
                    f"https://graph.facebook.com/v19.0/{container_id}",
                    params={"fields": "status_code", "access_token": access_token}
                )
                if status_res.json().get("status_code") == "FINISHED":
                    break
                await asyncio.sleep(3)

        # 3. Create carousel container
        carousel_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": access_token
            }
        )
        carousel_res.raise_for_status()
        carousel_id = carousel_res.json().get("id")

        # 4. Publish carousel
        pub_res = await client.post(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
            params={"creation_id": carousel_id, "access_token": access_token}
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
