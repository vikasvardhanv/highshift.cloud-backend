import httpx
from app.utils.logger import logger
import urllib.parse
import base64

# Pinterest API (v5)
AUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
API_BASE = "https://api.pinterest.com/v5"

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(scopes),
        "state": state
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"{AUTH_URL}?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    auth_str = f"{client_id}:{client_secret}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    async with httpx.AsyncClient() as client:
        res = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
        )
        res.raise_for_status()
        return res.json()

async def get_user_info(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{API_BASE}/user_account",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        res.raise_for_status()
        return res.json()

async def create_pin(access_token: str, board_id: str, title: str, description: str, link: str = None, media_url: str = None):
    """
    Create a Pin. Reference: https://developers.pinterest.com/docs/api/v5/#operation/pins/create
    """
    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "media_source": {
            "source_type": "image_url",
            "url": media_url
        }
    }
    if link:
        payload["link"] = link
        
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{API_BASE}/pins",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        res.raise_for_status()
        return res.json()

async def get_boards(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{API_BASE}/boards",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        res.raise_for_status()
        return res.json().get("items", [])
