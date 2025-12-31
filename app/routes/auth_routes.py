from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
import uuid
import datetime
from app.utils.auth import get_current_user, get_optional_user, hash_key
from app.models.user import User, LinkedAccount
from app.models.oauth_state import OAuthState
from app.platforms import instagram, twitter, facebook, linkedin, youtube
from app.services.token_service import encrypt_token

from app.services.token_service import encrypt_token

# Add a simple helper to be used as a dependency
async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/connect", tags=["Auth"], dependencies=[Depends(ensure_db)])

@router.get("/{platform}")
async def connect_platform(
    platform: str, 
    user: User = Depends(get_optional_user)
):
    """
    Redirect the user to the platform's OAuth page.
    """
    state_id = str(uuid.uuid4())
    state_payload = state_id
    if user:
        state_payload = f"{state_id}:{str(user.id)}"
    
    state = state_payload
    
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
        
        code_verifier, code_challenge = twitter.generate_pkce_pair()
        
        # Store verifier in DB
        await OAuthState(state_id=state_id, code_verifier=code_verifier).insert()
        
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
):
    """
    Handle the OAuth redirection and exchange code for tokens.
    """
    state_parts = state.split(":")
    state_id = state_parts[0]
    user_id_from_state = state_parts[1] if len(state_parts) > 1 else None
    
    frontend_url = os.getenv("CORS_ORIGINS", "").split(",")[0] or "http://localhost:5173"

    try:
        if platform == "twitter":
            # 1. Retrieve verifier
            oauth_data = await OAuthState.find_one({"state_id": state_id})
            if not oauth_data:
                raise HTTPException(status_code=400, detail="Invalid or expired state")
            
            # 2. Exchange code for token
            token_data = await twitter.exchange_code(
                client_id=os.getenv("TWITTER_CLIENT_ID"),
                client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
                redirect_uri=os.getenv("TWITTER_REDIRECT_URI"),
                code=code,
                code_verifier=oauth_data.code_verifier
            )
            
            # 3. Get profile
            access_token = token_data.get("access_token")
            profile = await twitter.get_me(access_token)
            user_data = profile.get("data", {})
            
            account_id = user_data.get("id")
            username = user_data.get("username")
            display_name = user_data.get("name")
            
            # Prepare LinkedAccount
            linked_account = LinkedAccount(
                platform="twitter",
                accountId=account_id,
                username=username,
                displayName=display_name,
                accessTokenEnc=encrypt_token(access_token),
                refreshTokenEnc=encrypt_token(token_data.get("refresh_token")) if token_data.get("refresh_token") else None,
                expiresAt=datetime.datetime.utcnow() + datetime.timedelta(seconds=token_data.get("expires_in", 7200)),
                rawProfile=profile
            )

            # 4. Find or Create User
            api_key_to_return = None
            user = None
            
            if user_id_from_state:
                user = await User.get(user_id_from_state)
            
            if not user:
                # Check if this social account is already linked to SOME user
                user = await User.find_one({
                    "linkedAccounts.platform": "twitter",
                    "linkedAccounts.accountId": account_id
                })

            if not user:
                # Create NEW USER and generate API KEY
                api_key_to_return = f"hs_{uuid.uuid4().hex}"
                user = User(
                    apiKeyHash=hash_key(api_key_to_return),
                    linkedAccounts=[linked_account]
                )
                await user.insert()
            else:
                # Update existing user: Remove old version of this account if exists, then add new
                user.linked_accounts = [a for a in user.linked_accounts if not (a.platform == "twitter" and a.account_id == account_id)]
                user.linked_accounts.append(linked_account)
                await user.save()

            # Clean up state
            await oauth_data.delete()

            # 5. Redirect to frontend with data
            redirect_params = f"platform=twitter&accountId={account_id}"
            if api_key_to_return:
                redirect_params += f"&apiKey={api_key_to_return}"
            
            return RedirectResponse(url=f"{frontend_url}/auth/callback?{redirect_params}")

        # Fallback for other platforms (similar logic needed)
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=unsupported_platform")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error={str(e)}")
