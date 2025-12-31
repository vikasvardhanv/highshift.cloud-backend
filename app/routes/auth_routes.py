from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
import uuid
from app.utils.auth import get_current_user
from app.models.user import User
from app.platforms import instagram # Example platform
from app.services.token_service import encrypt_token

router = APIRouter(prefix="/connect", tags=["Auth"])

@router.get("/{platform}")
async def connect_platform(
    platform: str, 
    user: User = Depends(get_current_user)
):
    """
    Redirect the user to the platform's OAuth page.
    """
    state = str(uuid.uuid4())
    # In a real app, store 'state' in DB/Redis and verify in callback
    
    if platform == "instagram":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
        scopes = os.getenv("INSTAGRAM_SCOPES", "").split(",")
        url = await instagram.get_auth_url(client_id, redirect_uri, state, scopes)
        return {"url": url}
    
    raise HTTPException(status_code=400, detail=f"Platform {platform} not supported yet")

@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str = Query(...),
    # userId would typically come from 'state' or session cookie
):
    """
    Handle the OAuth redirection and exchange code for tokens.
    """
    if platform == "instagram":
        # 1. Exchange code for token
        token_data = await instagram.exchange_code(
            client_id=os.getenv("FACEBOOK_APP_ID"),
            client_secret=os.getenv("FACEBOOK_APP_SECRET"),
            redirect_uri=os.getenv("INSTAGRAM_REDIRECT_URI"),
            code=code
        )
        # 2. Get profile and save (to be implemented in auth_service)
        return {"token_data": token_data, "message": "Account linked (simulated)"}

    return {"status": "success", "platform": platform}
