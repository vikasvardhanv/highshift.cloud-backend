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
    return f"https://www.facebook.com/v24.0/dialog/oauth?{'&'.join([f'{k}={v}' for k,v in params.items()])}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://graph.facebook.com/v24.0/oauth/access_token",
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
        create_res = await client.post(
            f"https://graph.facebook.com/v24.0/{ig_user_id}/media",
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
            f"https://graph.facebook.com/v24.0/{ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token
            }
        )
        pub_res.raise_for_status()
        return pub_res.json()
