import httpx
import hashlib
import base64
import os
from app.utils.logger import logger

def generate_pkce_pair():
    """Generate code verifier and challenge for PKCE."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8").replace("=", "")
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode("utf-8").replace("=", "")
    return code_verifier, code_challenge

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list, code_challenge: str):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    encoded_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"https://twitter.com/i/oauth2/authorize?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str, code_verifier: str):
    async with httpx.AsyncClient() as client:
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        res = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "client_id": client_id,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": code_verifier
            }
        )
        res.raise_for_status()
        return res.json()

async def refresh_access_token(client_id: str, client_secret: str, refresh_token: str):
    """Refresh an expired Twitter access token using the refresh token."""
    async with httpx.AsyncClient() as client:
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        res = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
        )
        res.raise_for_status()
        return res.json()

async def upload_media(access_token: str, file_path: str = None, media_data: bytes = None):
    """
    Upload media to Twitter (v1.1 API) and return media_id.
    Requires either file_path or media_data (bytes).
    """
    import os
    
    url = "https://upload.twitter.com/1.1/media/upload.json"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    data = None
    files = None
    
    if file_path:
        # Read file
        files = {"media": open(file_path, "rb")}
    elif media_data:
        files = {"media": media_data}
    else:
        raise ValueError("Either file_path or media_data must be provided")

    async with httpx.AsyncClient() as client:
        # 1. INIT
        init_data = {
            "command": "INIT",
            "total_bytes": os.path.getsize(file_path) if file_path else len(media_data),
            "media_type": "image/jpeg" # Defaulting to jpeg, should ideally detect
        }
        res = await client.post(url, headers=headers, data=init_data)
        res.raise_for_status()
        media_id = res.json()["media_id_string"]
        
        # 2. APPEND
        # Twitter requires multipart/form-data for APPEND
        append_data = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": 0
        }
        # Note: For larger files, we need chunked upload. Assuming small files for now (< 5MB)
        res = await client.post(url, headers=headers, data=append_data, files=files)
        res.raise_for_status()
        
        # 3. FINALIZE
        finalize_data = {
            "command": "FINALIZE",
            "media_id": media_id
        }
        res = await client.post(url, headers=headers, data=finalize_data)
        res.raise_for_status()
        
        return media_id

async def post_tweet(access_token: str, text: str, media_ids: list = None):
    async with httpx.AsyncClient() as client:
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
            
        res = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        res.raise_for_status()
        return res.json()

async def get_me(access_token: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"user.fields": "profile_image_url,description"}
        )
        res.raise_for_status()
        return res.json()
