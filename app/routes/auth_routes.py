from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
import uuid
from app.utils.auth import get_current_user
from app.models.user import User
from app.platforms import instagram, twitter, facebook, linkedin, youtube
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
        return {"authUrl": url}
    
    if platform == "twitter":
        client_id = os.getenv("TWITTER_CLIENT_ID")
        redirect_uri = os.getenv("TWITTER_REDIRECT_URI")
        scopes = os.getenv("TWITTER_SCOPES", "tweet.read,tweet.write,users.read,offline.access").split(",")
        
        # Note: In a real app, store code_verifier linked to state
        code_verifier, code_challenge = twitter.generate_pkce_pair()
        
        url = await twitter.get_auth_url(client_id, redirect_uri, state, scopes, code_challenge)
        return {"authUrl": url}

    if platform == "facebook":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
        scopes = os.getenv("FACEBOOK_SCOPES", "pages_manage_posts,pages_read_engagement").split(",")
        url = await facebook.get_auth_url(client_id, redirect_uri, state, scopes)
        return {"authUrl": url}

    if platform == "linkedin":
        client_id = os.getenv("LINKEDIN_CLIENT_ID")
        redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
        scopes = os.getenv("LINKEDIN_SCOPES", "w_member_social,r_liteprofile").split(",")
        url = await linkedin.get_auth_url(client_id, redirect_uri, state, scopes)
        return {"authUrl": url}

    if platform == "youtube":
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        scopes = os.getenv("GOOGLE_SCOPES", "https://www.googleapis.com/auth/youtube.upload").split(",")
        url = await youtube.get_auth_url(client_id, redirect_uri, state, scopes)
        return {"authUrl": url}
    
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
