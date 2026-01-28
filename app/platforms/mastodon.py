import httpx
from app.utils.logger import logger

# Mastodon is decentralized, so BASE_URL depends on the instance.
# We will require the instance URL to be passed.

async def get_app_credentials(instance_url: str, client_name: str, redirect_uri: str, website: str = None):
    """
    Register the app on the instance to get client_id and client_secret.
    """
    url = f"{instance_url.rstrip('/')}/api/v1/apps"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data={
            "client_name": client_name,
            "redirect_uris": redirect_uri,
            "scopes": "read write push",
            "website": website or ""
        })
        res.raise_for_status()
        return res.json()

async def get_auth_url(instance_url: str, client_id: str, redirect_uri: str, scopes: list = ["read", "write"]):
    """
    Generate auth URL for the user.
    """
    scope_str = " ".join(scopes)
    return f"{instance_url.rstrip('/')}/oauth/authorize?client_id={client_id}&scope={scope_str}&redirect_uri={redirect_uri}&response_type=code"

async def exchange_code(instance_url: str, client_id: str, client_secret: str, redirect_uri: str, code: str):
    url = f"{instance_url.rstrip('/')}/oauth/token"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
            "scope": "read write"
        })
        res.raise_for_status()
        return res.json()

async def get_account_verify_credentials(instance_url: str, access_token: str):
    url = f"{instance_url.rstrip('/')}/api/v1/accounts/verify_credentials"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
        res.raise_for_status()
        return res.json()

async def post_status(instance_url: str, access_token: str, status: str, media_ids: list = None):
    url = f"{instance_url.rstrip('/')}/api/v1/statuses"
    data = {"status": status}
    if media_ids:
        data["media_ids[]"] = media_ids
        
    async with httpx.AsyncClient() as client:
        res = await client.post(
            url, 
            headers={"Authorization": f"Bearer {access_token}"},
            data=data
        )
        res.raise_for_status()
        return res.json()

async def upload_media(instance_url: str, access_token: str, file_path: str, description: str = None):
    url = f"{instance_url.rstrip('/')}/api/v2/media"
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {}
            if description:
                data["description"] = description
            
            res = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                files=files,
                data=data
            )
            res.raise_for_status()
            return res.json() # Returns 'id'
