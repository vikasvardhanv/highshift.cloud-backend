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

async def upload_media(access_token: str, file_path: str = None, media_data: bytes = None, media_type: str = None):
    """
    Upload media to Twitter (v1.1 API) and return media_id.
    Requires either file_path or media_data (bytes).
    """
    import os
    import mimetypes
    
    url = "https://upload.twitter.com/1.1/media/upload.json"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    data = None
    files = None
    
    if file_path:
        # Read file
        files = {"media": open(file_path, "rb")}
        total_bytes = os.path.getsize(file_path)
        if not media_type:
             media_type, _ = mimetypes.guess_type(file_path)
    elif media_data:
        files = {"media": media_data}
        total_bytes = len(media_data)
    else:
        raise ValueError("Either file_path or media_data must be provided")

    if not media_type:
        media_type = "image/jpeg" # Fallback
        
    print(f"Uploading to Twitter: Type={media_type}, Bytes={total_bytes}")

    async with httpx.AsyncClient() as client:
        # 1. INIT
        init_data = {
            "command": "INIT",
            "total_bytes": total_bytes,
            "media_type": media_type,
            "media_category": "tweet_video" if "video" in media_type else "tweet_image"
        }
        res = await client.post(url, headers=headers, data=init_data)
        if res.status_code != 200 and res.status_code != 202:
             logger.error(f"Twitter INIT failed: {res.text}")
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
        # TODO: Implement chunked upload loop for reliability
        res = await client.post(url, headers=headers, data=append_data, files=files)
        if res.status_code != 200 and res.status_code != 202:
             logger.error(f"Twitter APPEND failed: {res.text}")
        res.raise_for_status()
        
        # 3. FINALIZE
        finalize_data = {
            "command": "FINALIZE",
            "media_id": media_id
        }
        res = await client.post(url, headers=headers, data=finalize_data)
        if res.status_code != 200 and res.status_code != 202:
             logger.error(f"Twitter FINALIZE failed: {res.text}")
        res.raise_for_status()
        
        # 4. STATUS (For video processing)
        if "video" in media_type:
            processing_info = res.json().get("processing_info")
            if processing_info:
                state = processing_info["state"]
                # Ideally poll until succeeded, but for simple MVP we return ID.
                # If state is pending, tweet creation might fail if done immediately.
                # Adding a small wait or simple poll could be good here.
                import asyncio
                while state in ["pending", "in_progress"]:
                    await asyncio.sleep(1) # Wait 1s
                    check_url = "https://upload.twitter.com/1.1/media/upload.json"
                    check_res = await client.get(check_url, headers=headers, params={"command": "STATUS", "media_id": media_id})
                    state = check_res.json().get("processing_info", {}).get("state")
                    if state == "failed":
                        logger.error(f"Twitter Video Processing Failed: {check_res.json()}")
                        raise Exception("Twitter Video Processing Failed")
        
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
