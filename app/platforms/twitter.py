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

async def upload_media(
    access_token: str, 
    file_path: str = None, 
    media_data: bytes = None, 
    media_type: str = None,
    # OAuth 1.0a credentials (required for v1.1 media upload)
    api_key: str = None,
    api_secret: str = None,
    access_token_oauth1: str = None,
    access_token_secret: str = None
):
    """
    Upload media to Twitter (v1.1 API) and return media_id.
    
    Twitter's media upload API requires OAuth 1.0a authentication.
    If OAuth 1.0a credentials are not provided, falls back to environment variables.
    """
    import os
    import mimetypes
    import requests
    from requests_oauthlib import OAuth1
    import asyncio
    
    url = "https://upload.twitter.com/1.1/media/upload.json"
    
    # Get OAuth 1.0a credentials
    api_key = api_key or os.getenv("TWITTER_API_KEY")
    api_secret = api_secret or os.getenv("TWITTER_API_SECRET")
    access_token_oauth1 = access_token_oauth1 or os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = access_token_secret or os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    
    if not all([api_key, api_secret, access_token_oauth1, access_token_secret]):
        logger.error("Twitter OAuth 1.0a credentials missing. Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
        raise ValueError("Twitter OAuth 1.0a credentials required for media upload")
    
    # Create OAuth 1.0a auth handler
    auth = OAuth1(api_key, api_secret, access_token_oauth1, access_token_secret)
    
    # Prepare media data
    if file_path:
        with open(file_path, "rb") as f:
            media_binary = f.read()
        total_bytes = os.path.getsize(file_path)
        if not media_type:
            media_type, _ = mimetypes.guess_type(file_path)
    elif media_data:
        media_binary = media_data
        total_bytes = len(media_data)
    else:
        raise ValueError("Either file_path or media_data must be provided")

    if not media_type:
        media_type = "image/jpeg"  # Fallback
    
    is_video = "video" in media_type
    media_category = "tweet_video" if is_video else "tweet_image"
        
    logger.info(f"Uploading to Twitter: Type={media_type}, Bytes={total_bytes}, Category={media_category}")

    # Run synchronous requests in executor to avoid blocking
    loop = asyncio.get_event_loop()
    
    def _upload():
        # 1. INIT
        init_data = {
            "command": "INIT",
            "total_bytes": total_bytes,
            "media_type": media_type,
            "media_category": media_category
        }
        res = requests.post(url, data=init_data, auth=auth)
        if res.status_code not in [200, 202]:
            logger.error(f"Twitter INIT failed: {res.status_code} - {res.text}")
            res.raise_for_status()
        media_id = res.json()["media_id_string"]
        logger.info(f"Twitter INIT success: media_id={media_id}")
        
        # 2. APPEND (chunked for large files, single chunk for small)
        CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
        segment_index = 0
        
        for i in range(0, len(media_binary), CHUNK_SIZE):
            chunk = media_binary[i:i + CHUNK_SIZE]
            append_data = {
                "command": "APPEND",
                "media_id": media_id,
                "segment_index": segment_index
            }
            files = {"media": chunk}
            res = requests.post(url, data=append_data, files=files, auth=auth)
            if res.status_code not in [200, 202, 204]:
                logger.error(f"Twitter APPEND failed: {res.status_code} - {res.text}")
                res.raise_for_status()
            segment_index += 1
        logger.info(f"Twitter APPEND success: {segment_index} segments")
        
        # 3. FINALIZE
        finalize_data = {
            "command": "FINALIZE",
            "media_id": media_id
        }
        res = requests.post(url, data=finalize_data, auth=auth)
        if res.status_code not in [200, 201, 202]:
            logger.error(f"Twitter FINALIZE failed: {res.status_code} - {res.text}")
            res.raise_for_status()
        logger.info(f"Twitter FINALIZE success")
        
        # 4. STATUS (For video processing)
        if is_video:
            processing_info = res.json().get("processing_info")
            if processing_info:
                import time
                state = processing_info.get("state")
                while state in ["pending", "in_progress"]:
                    wait_secs = processing_info.get("check_after_secs", 1)
                    time.sleep(wait_secs)
                    status_params = {"command": "STATUS", "media_id": media_id}
                    check_res = requests.get(url, params=status_params, auth=auth)
                    processing_info = check_res.json().get("processing_info", {})
                    state = processing_info.get("state")
                    logger.info(f"Twitter video processing: {state}")
                    if state == "failed":
                        error = processing_info.get("error", {})
                        logger.error(f"Twitter Video Processing Failed: {error}")
                        raise Exception(f"Twitter Video Processing Failed: {error}")
        
        return media_id
    
    media_id = await loop.run_in_executor(None, _upload)
    return media_id

async def post_tweet(access_token: str, text: str, media_ids: list = None):
    async with httpx.AsyncClient() as client:
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        
        logger.info(f"Twitter API request payload: {payload}")
            
        res = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        if res.status_code != 201:
            logger.error(f"Twitter API error: {res.status_code} - {res.text}")
        
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
