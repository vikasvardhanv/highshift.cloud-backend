import httpx
from app.utils.logger import logger

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    encoded_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"https://accounts.google.com/o/oauth2/v2/auth?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )
        res.raise_for_status()
        return res.json()

async def upload_video(access_token: str, title: str, description: str, privacy_status: str = "public"):
    # YouTube video upload is complex and requires multipart/related or resumable upload.
    # This is a placeholder for the API call structure.
    logger.info(f"YouTube upload requested for {title}")
    return {"status": "success", "message": "YouTube upload logic is a placeholder (requires video file processing)"}
