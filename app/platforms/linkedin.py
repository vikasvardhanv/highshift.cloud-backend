import httpx
from app.utils.logger import logger

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": " ".join(scopes)
    }
    encoded_params = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"https://www.linkedin.com/oauth/v2/authorization?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        res.raise_for_status()
        return res.json()

async def post_to_profile(access_token: str, person_urn: str, text: str):
    async with httpx.AsyncClient() as client:
        body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        res = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()

async def register_upload(access_token: str, person_urn: str):
    """
    Step 1: Register the image upload to get an upload URL.
    """
    async with httpx.AsyncClient() as client:
        body = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        res = await client.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()

async def upload_image(upload_url: str, image_data: bytes, access_token: str):
    """
    Step 2: Upload the binary image data to the URL from Step 1.
    Note: For the upload step, LinkedIn generally does not require the Bearer token in headers 
    if the upload URL is signed, but adding it doesn't hurt. Some docs say just PUT to the URL.
    """
    async with httpx.AsyncClient() as client:
        res = await client.put(
            upload_url,
            content=image_data,
            headers={"Authorization": f"Bearer {access_token}"} 
        )
        res.raise_for_status()
        return True

async def post_with_media(access_token: str, person_urn: str, text: str, asset_urn: str):
    """
    Step 3: Create the UGC post referencing the uploaded asset URN.
    """
    async with httpx.AsyncClient() as client:
        body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": text},
                            "media": asset_urn,
                            "title": {"text": text[:200]} # Title is optional but good to have
                        }
                    ]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        res = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()
