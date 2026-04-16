import hashlib
import os
import json
from datetime import datetime, timedelta
from typing import Optional
from types import SimpleNamespace

from fastapi import Security, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.db.postgres import fetch_user_by_api_key_hash, fetch_user_by_id, update_user


def _normalize_json_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    return []


class AuthUser(SimpleNamespace):
    """
    Runtime user object used across routes/services.
    Mimics prior Beanie object shape and provides async save().
    """

    async def save(self):
        linked_accounts = []
        for a in (getattr(self, "linked_accounts", []) or []):
            if isinstance(a, dict):
                linked_accounts.append(a)
            else:
                linked_accounts.append(
                    {
                        "platform": getattr(a, "platform", None),
                        "accountId": getattr(a, "account_id", None),
                        "username": getattr(a, "username", None),
                        "displayName": getattr(a, "display_name", None),
                        "accessTokenEnc": getattr(a, "access_token_enc", None),
                        "refreshTokenEnc": getattr(a, "refresh_token_enc", None),
                        "expiresAt": (
                            getattr(a, "expires_at", None).isoformat()
                            if hasattr(getattr(a, "expires_at", None), "isoformat")
                            else getattr(a, "expires_at", None)
                        ),
                        "profileId": getattr(a, "profile_id", None),
                        "rawProfile": getattr(a, "raw_profile", None),
                        "picture": getattr(a, "picture", None),
                    }
                )

        profiles = []
        for p in (getattr(self, "profiles", []) or []):
            if isinstance(p, dict):
                profiles.append(p)
            else:
                profiles.append(
                    {
                        "id": getattr(p, "id", None),
                        "name": getattr(p, "name", None),
                        "created_at": (
                            getattr(p, "created_at", None).isoformat()
                            if hasattr(getattr(p, "created_at", None), "isoformat")
                            else getattr(p, "created_at", None)
                        ),
                    }
                )

        api_keys = []
        for k in (getattr(self, "api_keys", []) or []):
            if isinstance(k, dict):
                api_keys.append(k)
            else:
                api_keys.append(
                    {
                        "id": getattr(k, "id", None),
                        "name": getattr(k, "name", "Default Key"),
                        "keyHash": getattr(k, "key_hash", None),
                        "created_at": getattr(k, "created_at", None),
                        "lastUsed": getattr(k, "last_used", None),
                    }
                )

        payload = {
            "id": str(self.id),
            "email": getattr(self, "email", None),
            "password_hash": getattr(self, "password_hash", None),
            "google_id": getattr(self, "google_id", None),
            "api_key_hash": getattr(self, "api_key_hash", None),
            "api_keys": api_keys,
            "linked_accounts": linked_accounts,
            "profiles": profiles,
            "developer_keys": getattr(self, "developer_keys", {}) or {},
            "plan_tier": getattr(self, "plan_tier", "starter"),
            "max_profiles": getattr(self, "max_profiles", 50),
        }
        await update_user(str(self.id), payload)


def _to_auth_user(row: dict) -> AuthUser:
    api_keys = []
    for k in _normalize_json_list(row.get("api_keys")):
        if not isinstance(k, dict):
            continue
        api_keys.append(
            SimpleNamespace(
                id=k.get("id"),
                name=k.get("name", "Default Key"),
                key_hash=k.get("keyHash") or k.get("key_hash"),
                created_at=k.get("created_at") or k.get("createdAt"),
                last_used=k.get("lastUsed") or k.get("last_used"),
            )
        )

    linked_accounts = []
    for item in _normalize_json_list(row.get("linked_accounts")):
        if not isinstance(item, dict):
            continue
        linked_accounts.append(
            SimpleNamespace(
                platform=item.get("platform"),
                account_id=item.get("accountId") or item.get("account_id"),
                username=item.get("username"),
                display_name=item.get("displayName") or item.get("display_name"),
                access_token_enc=item.get("accessTokenEnc") or item.get("access_token_enc"),
                refresh_token_enc=item.get("refreshTokenEnc") or item.get("refresh_token_enc"),
                expires_at=item.get("expiresAt") or item.get("expires_at"),
                profile_id=item.get("profileId") or item.get("profile_id"),
                raw_profile=item.get("rawProfile") or item.get("raw_profile"),
                picture=item.get("picture"),
            )
        )

    return AuthUser(
        id=str(row.get("id")),
        email=row.get("email"),
        password_hash=row.get("password_hash"),
        google_id=row.get("google_id"),
        api_key_hash=row.get("api_key_hash"),
        api_keys=api_keys,
        linked_accounts=linked_accounts,
        profiles=[
            SimpleNamespace(
                id=p.get("id"),
                name=p.get("name"),
                created_at=p.get("created_at"),
            )
            for p in _normalize_json_list(row.get("profiles"))
            if isinstance(p, dict)
        ],
        developer_keys=row.get("developer_keys") or {},
        plan_tier=row.get("plan_tier") or "starter",
        max_profiles=row.get("max_profiles") or 50,
    )

# --- Configuration ---
# You should ensure JWT_SECRET is set in .env
JWT_SECRET = os.getenv("JWT_SECRET", "changethis_secret_key_please") 
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24 * 7  # 7 days

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
security_bearer = HTTPBearer(auto_error=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_key(key: str) -> str:
    """Hash the API key (matching Node.js logic if possible)."""
    return hashlib.sha256(key.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
):
    """
    FastAPI dependency to validate API key OR JWT Header and return the User.
    """
    
    # 1. Check Bearer Token (JWT) - Priority for Frontend
    if bearer and bearer.credentials:
        try:
            token = bearer.credentials
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id:
                user_row = await fetch_user_by_id(user_id)
                if user_row:
                    return _to_auth_user(user_row)
        except JWTError as e:
            print(f"JWT Verification Failed: {str(e)}")
            pass # Fallback to checking API Key

    # 2. Check API Key - Priority for API access
    if api_key:
        hashed = hash_key(api_key)
        try:
            user_row = await fetch_user_by_api_key_hash(hashed)
            if user_row:
                # B2B Audit: update lastUsed in json list if matching nested API key hash
                keys = _normalize_json_list(user_row.get("api_keys"))
                changed = False
                for k in keys:
                    if not isinstance(k, dict):
                        continue
                    if k.get("keyHash") == hashed:
                        k["lastUsed"] = datetime.utcnow().isoformat()
                        changed = True
                        break
                if changed:
                    user_row["api_keys"] = keys
                    await update_user(str(user_row["id"]), user_row)
                return _to_auth_user(user_row)
        except Exception as e:
            print(f"Auth Error (User Load Failed): {e}")

    # 3. Fail if neither found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )

async def get_optional_user(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
):
    """
    FastAPI dependency to optionally return a User.
    """
    try:
        if bearer and bearer.credentials:
            payload = jwt.decode(bearer.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user_row = await fetch_user_by_id(user_id)
                if user_row:
                    return _to_auth_user(user_row)
        
        if api_key:
            hashed = hash_key(api_key)
            user_row = await fetch_user_by_api_key_hash(hashed)
            if user_row:
                return _to_auth_user(user_row)
    except Exception:
        pass
        
    return None
