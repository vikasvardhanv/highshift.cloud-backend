from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.responses import RedirectResponse
import os
import uuid
import datetime
from app.utils.auth import (
    get_current_user, 
    get_optional_user, 
    hash_key, 
    verify_password, 
    get_password_hash, 
    create_access_token
)
from app.models.user import User, LinkedAccount, ApiKey
from app.models.oauth_state import OAuthState
from app.platforms import instagram, twitter, facebook, linkedin, youtube
from app.services.token_service import encrypt_token

from pydantic import BaseModel, EmailStr

# Add a simple helper to be used as a dependency
async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/auth", tags=["Auth"], dependencies=[Depends(ensure_db)])

# --- Pydantic Models for Auth ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# --- Endpoints ---

@router.post("/register")
async def register(user_data: UserRegister):
    import logging
    logger = logging.getLogger("auth")
    logger.setLevel(logging.INFO)
    
    # Normalize email
    email = user_data.email.strip().lower()
    logger.info(f"Registering user: {email}")

    # Check if user exists (Case insensitive lookup)
    existing_user = await User.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
    if existing_user:
        logger.warning(f"Registration failed: Email {email} already exists")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_pwd = get_password_hash(user_data.password.strip()) # Strip whitespace from password
    logger.info(f"Generated hash for {email}: {hashed_pwd}")
    api_key_str = f"hs_{uuid.uuid4().hex}"
    
    new_user = User(
        email=email, # Save normalized email
        passwordHash=hashed_pwd,
        apiKeyHash=hash_key(api_key_str),
        apiKeys=[ApiKey(name="Default Key", keyHash=hash_key(api_key_str))]
    )
    await new_user.insert()
    
    # Generate JWT
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "api_key": api_key_str # Return API key once on registration
    }

@router.post("/login")
async def login(user_data: UserLogin):
    import logging
    logger = logging.getLogger("auth")
    
    # Normalize input
    email = user_data.email.strip()
    # Note: We DON'T lower() here for the search query immediately because we want to support 
    # finding the user even if stored with mixed case, but we use regex 'i' to match any case.
    
    logger.info(f"Login attempt for: {email}")

    # Case-insensitive search
    user = await User.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
    if not user:
        logger.warning(f"Login failed: User {email} not found")
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not user.password_hash:
        logger.warning(f"Login failed: User {email} has no password hash (likely OAuth only)")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password (strip input)
    is_valid = verify_password(user_data.password.strip(), user.password_hash)
    if not is_valid:
        logger.warning(f"Login failed: Invalid password for {user_data.email}")
        logger.info(f"User ID: {user.id}")
        logger.info(f"Stored Hash: {user.password_hash}")
        # logger.info(f"Input Pwd: {user_data.password}") # SECURITY RISK: Don't log passwords
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer"
    }

@router.get("/me")
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Return the current logged-in user's information."""
    # Derive display name from email if available
    name = None
    initials = "U"
    
    if user.email:
        # Extract name from email (e.g., vikash.vardhan@example.com -> Vikash Vardhan)
        email_prefix = user.email.split("@")[0]
        # Convert underscore/dots to spaces and title case
        name_parts = email_prefix.replace(".", " ").replace("_", " ").split()
        name = " ".join(part.capitalize() for part in name_parts)
        
        # Generate initials from name parts
        if len(name_parts) >= 2:
            initials = (name_parts[0][0] + name_parts[-1][0]).upper()
        elif len(name_parts) == 1:
            initials = name_parts[0][:2].upper()
    
    return {
        "id": str(user.id),
        "email": user.email,
        "name": name or "User",
        "initials": initials,
        "planTier": user.plan_tier,
        "maxProfiles": user.max_profiles,
        "linkedAccountsCount": len(user.linked_accounts),
        "profilesCount": len(user.profiles)
    }

@router.get("/google")
async def google_login():
    """Start Google OAuth flow for Login (not YouTube channel linking)."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URL_LOGIN", os.getenv("CORS_ORIGINS", "").split(",")[0] + "/auth/callback") # Default or specific env
    # Note: If separate redirect needed, assume backend handles it. 
    # For now, let's reuse the logic but with a specific state to distinguish login vs linking if needed.
    # Actually, standard Google Login usually uses a simpler scope: openid email profile
    
    # We'll use a backend callback for security, then redirect to frontend
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        # Fallback for local development if not set, but warn
        backend_url = "http://localhost:3000"
        
    backend_redirect_uri = f"{backend_url}/auth/google/callback"
    
    state = str(uuid.uuid4())
    scopes = ["openid", "email", "profile"]
    
    scope_str = " ".join(scopes)
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"response_type=code&client_id={client_id}&redirect_uri={backend_redirect_uri}&"
        f"scope={scope_str}&state={state}&access_type=offline&prompt=consent"
    )
    
    return RedirectResponse(auth_url)

@router.get("/google/callback")
async def google_callback(code: str, state: str):
    import httpx
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    backend_redirect_uri = f"{os.getenv('BACKEND_URL', 'http://localhost:3000')}/auth/google/callback"
    
    # DETERMINE FRONTEND URL
    # Priority:
    # 1. FRONTEND_URL env var (Explicit override)
    # 2. CORS_ORIGINS (Split by comma, take first)
    # 3. Default to localhost
    
    frontend_url = os.getenv("FRONTEND_URL")
    if not frontend_url:
        origins = os.getenv("CORS_ORIGINS", "").split(",")
        frontend_url = origins[0] if origins and origins[0] else "http://localhost:5173"

    # Fix: If production and 'http' is found in CORS_ORIGINS but not localhost, force HTTPS
    if "highshift.cloud" in frontend_url and frontend_url.startswith("http://"):
        frontend_url = frontend_url.replace("http://", "https://")


    async with httpx.AsyncClient() as client:
        # Exchange code
        token_res = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": backend_redirect_uri,
        })
        token_data = token_res.json()
        
        if "error" in token_data:
             return RedirectResponse(f"{frontend_url}/login?error=google_auth_failed")
             
        access_token = token_data["access_token"]
        
        # Get Profile
        user_info_res = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
            "Authorization": f"Bearer {access_token}"
        })
        user_info = user_info_res.json()
        
        google_id = user_info["id"]
        email = user_info["email"]
        
        # Find or Create User
        user = await User.find_one({"$or": [{"googleId": google_id}, {"email": email}]})
        
        if not user:
            # Create new
            api_key_str = f"hs_{uuid.uuid4().hex}"
            user = User(
                email=email,
                googleId=google_id,
                apiKeyHash=hash_key(api_key_str),
                apiKeys=[ApiKey(name="Default Key", keyHash=hash_key(api_key_str))]
            )
            await user.insert()
        else:
            # Link Google ID if only email matched
            if not user.google_id:
                user.google_id = google_id
                await user.save()
        
        # Generate JWT
        jwt_token = create_access_token(data={"sub": str(user.id)})
        
        # Redirect to Frontend with Token
        return RedirectResponse(f"{frontend_url}/auth/callback?token={jwt_token}")


@router.get("/connect/{platform}")
async def connect_platform(
    platform: str, 
    profile_id: str = Query(None), # Add profile_id support
    user: User = Depends(get_optional_user)
):
    """
    Redirect the user to the platform's OAuth page.
    """
    state_id = str(uuid.uuid4())
    state_payload = state_id
    
    # Store profile_id in state if present
    if user:
        state_payload = f"{state_id}:{str(user.id)}"
        if profile_id:
            state_payload += f":{profile_id}"
    
    state = state_payload
    
    if platform == "instagram":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
        
        # Instagram Business requires Facebook Page permissions + Instagram permissions
        default_ig_scopes = [
            "instagram_basic", 
            "instagram_content_publish", 
            "pages_show_list", 
            "pages_read_engagement"
        ]
        
        env_scopes = os.getenv("INSTAGRAM_SCOPES", "").split(",")
        final_scopes = list(set(default_ig_scopes + [s for s in env_scopes if s]))
        
        url = await instagram.get_auth_url(client_id, redirect_uri, state, final_scopes)
        return {"authUrl": url}

    if platform == "twitter":
        client_id = os.getenv("TWITTER_CLIENT_ID")
        redirect_uri = os.getenv("TWITTER_REDIRECT_URI")
        
        # Validate required environment variables
        if not client_id:
            raise HTTPException(status_code=500, detail="TWITTER_CLIENT_ID not configured")
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="TWITTER_REDIRECT_URI not configured")
        
        scopes = os.getenv("TWITTER_SCOPES", "tweet.read,tweet.write,users.read,offline.access").split(",")
        
        try:
            # Explicitly ensure DB is initialized (fixing CollectionWasNotInitialized)
            from main import ensure_beanie_initialized
            await ensure_beanie_initialized()
            
            code_verifier, code_challenge = twitter.generate_pkce_pair()
            
            # Store verifier in DB
            oauth_state = OAuthState(state_id=state_id, code_verifier=code_verifier)
            await oauth_state.insert()
            
            url = await twitter.get_auth_url(client_id, redirect_uri, state, scopes, code_challenge)
            return {"authUrl": url}
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Twitter Auth Error [{type(e).__name__}]: {repr(e)}")
            print(f"Full traceback: {error_trace}")
            error_msg = str(e) or repr(e) or type(e).__name__
            raise HTTPException(status_code=500, detail=f"Twitter OAuth setup failed: {error_msg}")

    if platform == "facebook":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
        
        # Pure Facebook Scopes - NO Instagram scopes here to prevent "Invalid Scope" if product missing
        default_fb_scopes = [
            "public_profile", 
            # "email", # Removed to avoid "Invalid Scope" error if not enabled in App
            "pages_show_list", 
            "pages_manage_posts", 
            "pages_read_engagement"
        ]
        
        env_scopes = os.getenv("FACEBOOK_SCOPES", "").split(",")
        # Combine unique, filtering out any accidental instagram ones from env if mixed
        final_scopes = list(set(default_fb_scopes + [s for s in env_scopes if s and "instagram" not in s]))
        
        url = await facebook.get_auth_url(client_id, redirect_uri, state, final_scopes)
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

# Support both /auth/{platform}/callback AND /connect/{platform}/callback
@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    denied: str = Query(None) # Twitter sometimes sends 'denied' on cancellation
):
    """
    Handle the OAuth redirection and exchange code for tokens.
    """
    
    # DETERMINE FRONTEND URL
    # Priority:
    # 1. FRONTEND_URL env var (Explicit override)
    # 2. CORS_ORIGINS (Split by comma, take first)
    # 3. Default to localhost
    
    frontend_url = os.getenv("FRONTEND_URL")
    if not frontend_url:
        origins = os.getenv("CORS_ORIGINS", "").split(",")
        frontend_url = origins[0] if origins and origins[0] else "http://localhost:5173"

    # Fix: If production and 'http' is found in CORS_ORIGINS but not localhost, force HTTPS
    if "highshift.cloud" in frontend_url and frontend_url.startswith("http://"):
        frontend_url = frontend_url.replace("http://", "https://")


    # Handle Cancellation / Errors
    if error:
        return RedirectResponse(f"{frontend_url}/dashboard?error={error}")
    if denied:
        return RedirectResponse(f"{frontend_url}/dashboard?error=access_denied")
    if not code:
         return RedirectResponse(f"{frontend_url}/dashboard?error=no_code_provided")
         
    state_parts = state.split(":")
    state_id = state_parts[0]
    user_id_from_state = state_parts[1] if len(state_parts) > 1 else None
    profile_id_from_state = state_parts[2] if len(state_parts) > 2 else None
    
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
                rawProfile=profile,
                profileId=profile_id_from_state # Assign profile
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
                # Update existing user
                
                # Check if this specific account is already linked (update case)
                existing_account = next((a for a in user.linked_accounts if a.platform == "twitter" and a.account_id == account_id), None)
                
                if not existing_account:
                    # New account - Check Limits
                    if len(user.linked_accounts) >= user.max_profiles:
                        return RedirectResponse(
                            url=f"{frontend_url}/auth/callback?error=Plan Limit Reached: Max {user.max_profiles} profiles allow. Upgrade to add more."
                        )

                # Remove old version if exists, then add new
                user.linked_accounts = [a for a in user.linked_accounts if not (a.platform == "twitter" and a.account_id == account_id)]
                user.linked_accounts.append(linked_account)
                await user.save()

            # Clean up state
            await oauth_data.delete()

            # 5. Generate JWT for authentication
            jwt_token = create_access_token(data={"sub": str(user.id)})

            # 6. Redirect to frontend with data
            redirect_params = f"platform=twitter&accountId={account_id}&token={jwt_token}"
            if api_key_to_return:
                redirect_params += f"&apiKey={api_key_to_return}"
            
            return RedirectResponse(url=f"{frontend_url}/auth/callback?{redirect_params}")

        # Fallback for other platforms (similar logic needed)
        if platform == "facebook":
            # 1. Exchange code
            # Define Scopes Explicitly - these should match what get_auth_url uses
            token_data = await facebook.exchange_code(
                client_id=os.getenv("FACEBOOK_APP_ID"),
                client_secret=os.getenv("FACEBOOK_APP_SECRET"),
                redirect_uri=os.getenv("FACEBOOK_REDIRECT_URI"),
                code=code
            )
            user_access_token = token_data.get("access_token")
            
            if not user_access_token:
                 return RedirectResponse(f"{frontend_url}/auth/callback?error=Failed to get Access Token from Facebook.")

            # 2. Get Pages (Accounts)
            # We must post to Pages, not User Profile.
            pages = await facebook.get_accounts(user_access_token)
            
            if not pages:
                return RedirectResponse(f"{frontend_url}/auth/callback?error=No Facebook Pages found. You must manage a Page to post. Data: {len(pages)}")

            # 3. Find/Create User (Logic: If user logged in, use them. Else find by first page ID match or create)
            user = None
            if user_id_from_state:
                user = await User.get(user_id_from_state)
            
            if not user:
                # Try to find user linked to ANY of these pages
                page_ids = [p["id"] for p in pages]
                user = await User.find_one({
                    "linkedAccounts.platform": "facebook",
                    "linkedAccounts.accountId": {"$in": page_ids}
                })

            api_key_to_return = None
            new_user = False
            if not user:
                api_key_to_return = f"hs_{uuid.uuid4().hex}"
                user = User(
                    apiKeyHash=hash_key(api_key_to_return),
                    linkedAccounts=[] # Will fill below
                )
                new_user = True
            
            # Check Plan Limits before adding/updating (Simplify: just enforce max profiles count on save)
            
            # 4. Link All Pages
            # We replace existing FB pages or append new ones. 
            # Strategy: Upkeep user.linked_accounts list.
            
            current_fb_accounts = {a.account_id: a for a in user.linked_accounts if a.platform == "facebook"}
            
            added_count = 0
            for page in pages:
                p_id = page["id"]
                p_name = page["name"]
                p_token = page["access_token"] # PAGE Access Token
                p_pic = page.get("picture", {}).get("data", {}).get("url")
                
                # Check limit if adding new
                if p_id not in current_fb_accounts and len(user.linked_accounts) >= user.max_profiles:
                    continue # Skip if limit reached
                
                linked_account = LinkedAccount(
                    platform="facebook",
                    accountId=p_id,
                    username=p_name, # Pages don't always have usernames, use Name
                    displayName=p_name,
                    picture=p_pic,
                    accessTokenEnc=encrypt_token(p_token), # Store PAGE Token
                    expiresAt=None, # Page tokens last forever? Or until user password change.
                    rawProfile=page,
                    profileId=profile_id_from_state
                )
                
                # Remove old if exists
                user.linked_accounts = [a for a in user.linked_accounts if not (a.platform == "facebook" and a.account_id == p_id)]
                user.linked_accounts.append(linked_account)
                added_count += 1
            
            if new_user:
                await user.insert()
            else:
                await user.save()

            if added_count == 0 and len(pages) > 0:
                 return RedirectResponse(f"{frontend_url}/auth/callback?error=Plan Limit Reached. Could not add pages.")

            # Redirect
            jwt_token = create_access_token(data={"sub": str(user.id)})
            redirect_params = f"platform=facebook&count={added_count}&token={jwt_token}"
            if api_key_to_return:
                redirect_params += f"&apiKey={api_key_to_return}"
            return RedirectResponse(url=f"{frontend_url}/auth/callback?{redirect_params}")

        if platform == "instagram":
            # 1. Exchange code
            token_data = await instagram.exchange_code(
                client_id=os.getenv("FACEBOOK_APP_ID"), 
                client_secret=os.getenv("FACEBOOK_APP_SECRET"),
                redirect_uri=os.getenv("INSTAGRAM_REDIRECT_URI"),
                code=code
            )
            user_access_token = token_data.get("access_token")
            
            # 2. Get Pages & Linked Instagram Accounts
            # We rely on facebook.get_accounts because the token allows access to /me/accounts
            pages = await facebook.get_accounts(user_access_token)
            
            if not pages:
                return RedirectResponse(f"{frontend_url}/auth/callback?error=No Facebook Pages found. Ensure your Instagram Professional account is connected to a Page.")

            # Filter for pages with instagram_business_account
            ig_accounts = []
            for p in pages:
                if "instagram_business_account" in p:
                    ig_data = p["instagram_business_account"]
                    ig_data["page_access_token"] = p["access_token"] # We need Page Token to publish to IG
                    ig_data["page_name"] = p["name"]
                    ig_accounts.append(ig_data)
            
            if not ig_accounts:
                return RedirectResponse(f"{frontend_url}/auth/callback?error=No Instagram Business Accounts found connected to your Pages.")

            # 3. Find/Create User
            user = None
            if user_id_from_state:
                user = await User.get(user_id_from_state)
            
            if not user:
                ig_ids = [ig["id"] for ig in ig_accounts]
                user = await User.find_one({
                    "linkedAccounts.platform": "instagram",
                    "linkedAccounts.accountId": {"$in": ig_ids}
                })

            api_key_to_return = None
            new_user = False
            if not user:
                api_key_to_return = f"hs_{uuid.uuid4().hex}"
                user = User(
                    apiKeyHash=hash_key(api_key_to_return),
                    linkedAccounts=[]
                )
                new_user = True
            
            # 4. Link All IG Accounts
            current_ig_accounts = {a.account_id: a for a in user.linked_accounts if a.platform == "instagram"}
            
            added_count = 0
            for ig in ig_accounts:
                ig_id = ig["id"]
                ig_username = ig.get("username", "instagram_user")
                ig_pic = ig.get("profile_picture_url")
                page_token = ig["page_access_token"]
                
                if ig_id not in current_ig_accounts and len(user.linked_accounts) >= user.max_profiles:
                    continue
                
                linked_account = LinkedAccount(
                    platform="instagram",
                    accountId=ig_id,
                    username=ig_username,
                    displayName=ig_username,
                    picture=ig_pic,
                    accessTokenEnc=encrypt_token(page_token), # Store PAGE Token
                    expiresAt=None, 
                    rawProfile=ig,
                    profileId=profile_id_from_state
                )
                
                user.linked_accounts = [a for a in user.linked_accounts if not (a.platform == "instagram" and a.account_id == ig_id)]
                user.linked_accounts.append(linked_account)
                added_count += 1
            
            if new_user:
                await user.insert()
            else:
                await user.save()

            if added_count == 0:
                 return RedirectResponse(f"{frontend_url}/auth/callback?error=Plan Limit Reached or No New Accounts.")

            # Redirect
            jwt_token = create_access_token(data={"sub": str(user.id)})
            redirect_params = f"platform=instagram&count={added_count}&token={jwt_token}"
            if api_key_to_return:
                redirect_params += f"&apiKey={api_key_to_return}"
            return RedirectResponse(url=f"{frontend_url}/auth/callback?{redirect_params}")

        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=unsupported_platform")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error={str(e)}")


# ============ Route Alias for /connect/{platform}/callback ============
# This is for backwards compatibility with existing Twitter Developer settings
from fastapi import APIRouter as ConnectRouter

connect_router = APIRouter(prefix="/connect", tags=["Connect Alias"], dependencies=[Depends(ensure_db)])

@connect_router.get("/{platform}/callback")
async def connect_oauth_callback(
    platform: str, 
    code: str = Query(None), 
    state: str = Query(None),
    error: str = Query(None),
    denied: str = Query(None)
):
    """Alias for /auth/{platform}/callback - forwards to main oauth_callback."""
    return await oauth_callback(platform, code, state, error, denied)


# ============ Password Reset Endpoints ============

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """
    Initiate password reset: Generate token and send email.
    """
    email = req.email.strip()
    
    # 1. Find User by Email (Case Insensitive)
    user = await User.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
    
    if not user:
        # Avoid user enumeration: pretend stats is success
        # In a real app, maybe delay response slightly to mitigate timing attacks
        return {"status": "success", "message": "If account exists, reset email sent."}
    
    # Generate Token (valid for 30 mins)
    reset_token = str(uuid.uuid4())
    user.reset_token = reset_token
    user.reset_token_expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    await user.save()
    
    # Construct Link
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    
    # Send Email
    from app.services.email_service import send_password_reset_email
    
    # Attempt to send email
    success = send_password_reset_email(user.email, reset_link)
    
    if not success:
         logger.error(f"Failed to send reset email to {user.email}")
         # Optionally expose error if internal testing, but safer to hide
    
    return {"status": "success", "message": "If account exists, reset email sent."}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """
    Reset password using valid token.
    """
    user = await User.find_one(User.reset_token == req.token)
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if not user.reset_token_expiry or user.reset_token_expiry < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired")
        
    # Update Password
    import logging
    logger = logging.getLogger("auth")
    
    hashed_pwd = get_password_hash(req.new_password)
    logger.info(f"Resetting password for {user.email}. User ID: {user.id}. New Hash: {hashed_pwd}")
    
    user.password_hash = hashed_pwd
    user.reset_token = None
    user.reset_token_expiry = None
    await user.save()
    
    return {"status": "success", "message": "Password updated successfully"}

