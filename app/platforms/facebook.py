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

async def post_to_page(access_token: str, page_id: str, message: str, link: str = None):
    async with httpx.AsyncClient() as client:
        params = {
            "message": message,
            "access_token": access_token
        }
        if link:
            params["link"] = link
            
        res = await client.post(
            f"https://graph.facebook.com/v24.0/{page_id}/feed",
            params=params
        )
        res.raise_for_status()
        return res.json()
