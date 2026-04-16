import datetime
import logging
import os
import uuid
from typing import Optional

import httpx
from fastapi import HTTPException
from app.models.user import User

from app.db.postgres import (
    delete_oauth_state,
    fetch_user_by_email_ci,
    fetch_user_by_google_or_email,
    insert_oauth_state,
    insert_user,
    update_user,
)
from app.platforms import (
    bluesky,
    facebook,
    instagram,
    linkedin,
    mastodon,
    pinterest,
    threads,
    tiktok,
    twitter,
    youtube,
)
from app.utils.auth import (
    create_access_token,
    get_password_hash,
    hash_key,
    verify_password,
)

logger = logging.getLogger(__name__)


def get_frontend_url() -> str:
    frontend_url = os.getenv("FRONTEND_URL")
    if not frontend_url:
        origins = os.getenv("CORS_ORIGINS", "").split(",")
        frontend_url = origins[0] if origins and origins[0] else "http://localhost:5173"

    # Legacy safety for prior deployments
    if "socialraven.meganai.cloud" in frontend_url and frontend_url.startswith("http://"):
        frontend_url = frontend_url.replace("http://", "https://")
    return frontend_url


def build_oauth_state_payload(user: Optional[object], profile_id: Optional[str]) -> tuple[str, str]:
    state_id = str(uuid.uuid4())
    state_payload = state_id
    if user:
        state_payload = f"{state_id}_{str(user.id)}"
        if profile_id:
            state_payload += f"_{profile_id}"
    return state_id, state_payload


async def register_local_user(email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    existing_user = await fetch_user_by_email_ci(normalized_email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pwd = get_password_hash(password.strip())
    api_key_str = f"hs_{uuid.uuid4().hex}"
    new_user = await insert_user(
        {
            "email": normalized_email,
            "password_hash": hashed_pwd,
            "api_key_hash": hash_key(api_key_str),
            "api_keys": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Default Key",
                    "keyHash": hash_key(api_key_str),
                    "created_at": datetime.datetime.utcnow().isoformat(),
                    "lastUsed": None,
                }
            ],
            "linked_accounts": [],
            "profiles": [],
            "developer_keys": {},
        }
    )
    access_token = create_access_token(data={"sub": str(new_user["id"])})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "api_key": api_key_str,
    }


async def login_local_user(email: str, password: str) -> dict:
    user = await fetch_user_by_email_ci(email.strip())
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        is_valid = verify_password(password.strip(), user.get("password_hash"))
    except Exception as err:
        # Handle legacy/corrupt hashes gracefully instead of returning 500.
        logger.warning("Password verification failed for user %s: %s", user.get("id"), err)
        is_valid = False
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(data={"sub": str(user["id"])})
    return {"access_token": access_token, "token_type": "bearer"}


def build_user_me_response(user: User) -> dict:
    name = None
    initials = "U"
    if user.email:
        email_prefix = user.email.split("@")[0]
        name_parts = email_prefix.replace(".", " ").replace("_", " ").split()
        name = " ".join(part.capitalize() for part in name_parts)
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
        "profilesCount": len(user.profiles),
    }


def build_google_login_url() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("YOUTUBE_GOOGLE_CLIENT_ID")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:3000")
    backend_redirect_uri = f"{backend_url}/auth/google/callback"
    state = str(uuid.uuid4())
    scope_str = "openid email profile"
    return (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"response_type=code&client_id={client_id}&redirect_uri={backend_redirect_uri}&"
        f"scope={scope_str}&state={state}&access_type=offline&prompt=consent"
    )


async def google_login_callback_redirect(code: str) -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("YOUTUBE_GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("YOUTUBE_GOOGLE_CLIENT_SECRET")
    backend_redirect_uri = f"{os.getenv('BACKEND_URL', 'http://localhost:3000')}/auth/google/callback"
    frontend_url = get_frontend_url()

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": backend_redirect_uri,
            },
        )
        token_data = token_res.json()
        if "error" in token_data:
            return f"{frontend_url}/login?error=google_auth_failed"

        access_token = token_data["access_token"]
        user_info_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_info_res.json()

    google_id = user_info["id"]
    email = user_info["email"]
    user = await fetch_user_by_google_or_email(google_id, email)

    if not user:
        api_key_str = f"hs_{uuid.uuid4().hex}"
        user = await insert_user(
            {
                "email": email,
                "google_id": google_id,
                "api_key_hash": hash_key(api_key_str),
                "api_keys": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Default Key",
                        "keyHash": hash_key(api_key_str),
                        "created_at": datetime.datetime.utcnow().isoformat(),
                        "lastUsed": None,
                    }
                ],
                "linked_accounts": [],
                "profiles": [],
                "developer_keys": {},
            }
        )
    elif not user.get("google_id"):
        user["google_id"] = google_id
        await update_user(user["id"], user)

    jwt_token = create_access_token(data={"sub": str(user["id"])})
    return f"{frontend_url}/auth/callback?token={jwt_token}"


async def get_platform_connect_payload(
    platform: str,
    state_id: str,
    state_payload: str,
    instance_url: Optional[str] = None,
) -> dict:
    if platform == "instagram":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")
        default_scopes = [
            "instagram_basic",
            "instagram_content_publish",
            "pages_show_list",
            "pages_read_engagement",
        ]
        env_scopes = os.getenv("INSTAGRAM_SCOPES", "").split(",")
        final_scopes = list(set(default_scopes + [s for s in env_scopes if s]))
        return {
            "authUrl": await instagram.get_auth_url(
                client_id, redirect_uri, state_payload, final_scopes
            )
        }

    if platform == "twitter":
        client_id = os.getenv("TWITTER_CLIENT_ID")
        redirect_uri = os.getenv("TWITTER_REDIRECT_URI")
        if not client_id:
            raise HTTPException(status_code=500, detail="TWITTER_CLIENT_ID not configured")
        if not redirect_uri:
            raise HTTPException(status_code=500, detail="TWITTER_REDIRECT_URI not configured")

        scopes = os.getenv(
            "TWITTER_SCOPES", "tweet.read,tweet.write,users.read,offline.access"
        ).split(",")
        code_verifier, code_challenge = twitter.generate_pkce_pair()
        await insert_oauth_state(state_id=state_id, code_verifier=code_verifier)
        return {
            "authUrl": await twitter.get_auth_url(
                client_id, redirect_uri, state_payload, scopes, code_challenge
            )
        }

    if platform == "facebook":
        client_id = os.getenv("FACEBOOK_APP_ID")
        redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")
        default_scopes = [
            "public_profile",
            "pages_show_list",
            "pages_manage_posts",
            "pages_read_engagement",
            "pages_manage_metadata",
            "pages_read_user_content",
            "business_management",
            "read_insights",
        ]
        env_scopes = os.getenv("FACEBOOK_SCOPES", "").split(",")
        final_scopes = list(
            set(default_scopes + [s for s in env_scopes if s and "instagram" not in s])
        )
        return {
            "authUrl": await facebook.get_auth_url(
                client_id, redirect_uri, state_payload, final_scopes
            )
        }

    if platform == "linkedin":
        client_id = os.getenv("LINKEDIN_CLIENT_ID")
        redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
        scopes = os.getenv("LINKEDIN_SCOPES", "openid,profile,w_member_social,email").split(",")
        return {
            "authUrl": await linkedin.get_auth_url(
                client_id, redirect_uri, state_payload, scopes
            )
        }

    if platform == "youtube":
        client_id = os.getenv("YOUTUBE_GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("YOUTUBE_GOOGLE_REDIRECT_URI")
        default_scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "openid",
            "profile",
            "email",
        ]
        env_scopes = os.getenv("YOUTUBE_GOOGLE_SCOPES", "").split(",")
        final_scopes = list(set(default_scopes + [s for s in env_scopes if s]))
        return {
            "authUrl": await youtube.get_auth_url(
                client_id, redirect_uri, state_payload, final_scopes
            )
        }

    if platform == "tiktok":
        client_key = os.getenv("TIKTOK_CLIENT_KEY")
        redirect_uri = os.getenv("TIKTOK_REDIRECT_URI")
        scopes = os.getenv(
            "TIKTOK_SCOPES",
            "user.info.basic,user.info.profile,user.info.stats,video.publish,video.upload",
        ).split(",")
        if not client_key or not redirect_uri:
            raise HTTPException(status_code=500, detail="TikTok credentials not configured")
        return {
            "authUrl": await tiktok.get_auth_url(
                client_key, redirect_uri, state_payload, scopes
            )
        }

    if platform == "pinterest":
        client_id = os.getenv("PINTEREST_APP_ID")
        redirect_uri = os.getenv("PINTEREST_REDIRECT_URI")
        scopes = os.getenv("PINTEREST_SCOPES", "boards:read,pins:read,pins:write").split(",")
        if not client_id or not redirect_uri:
            raise HTTPException(status_code=500, detail="Pinterest credentials not configured")
        return {
            "authUrl": await pinterest.get_auth_url(
                client_id, redirect_uri, state_payload, scopes
            )
        }

    if platform == "threads":
        client_id = os.getenv("THREADS_APP_ID", os.getenv("FACEBOOK_APP_ID"))
        redirect_uri = os.getenv("THREADS_REDIRECT_URI")
        scopes = os.getenv("THREADS_SCOPES", "threads_basic,threads_content_publish").split(",")
        if not client_id or not redirect_uri:
            raise HTTPException(status_code=500, detail="Threads credentials not configured")
        return {
            "authUrl": await threads.get_auth_url(
                client_id, redirect_uri, state_payload, scopes
            )
        }

    if platform == "bluesky":
        return {"action": "show_form", "fields": ["handle", "app_password"]}

    if platform == "mastodon":
        if not instance_url:
            return {"action": "show_form", "fields": ["instance_url"]}

        redirect_uri = os.getenv(
            "MASTODON_REDIRECT_URI", f"{os.getenv('BACKEND_URL')}/auth/mastodon/callback"
        )
        app_data = await mastodon.get_app_credentials(
            instance_url, "Social Raven", redirect_uri, os.getenv("FRONTEND_URL")
        )
        await insert_oauth_state(
            state_id=state_id,
            extra_data={
                "instance_url": instance_url,
                "client_id": app_data["client_id"],
                "client_secret": app_data["client_secret"],
                "redirect_uri": redirect_uri,
            },
        )
        return {
            "authUrl": await mastodon.get_auth_url(
                instance_url, app_data["client_id"], redirect_uri
            )
        }

    raise HTTPException(status_code=400, detail=f"Platform {platform} not supported yet")
