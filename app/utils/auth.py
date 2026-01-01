import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Security, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.models.user import User

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
                user = await User.get(user_id)
                if user:
                    return user
        except JWTError:
            pass # Fallback to checking API Key if JWT fails (or could raise 401 directly)

    # 2. Check API Key - Priority for API access
    if api_key:
        hashed = hash_key(api_key)
        try:
            user = await User.find_one({"$or": [{"apiKeyHash": hashed}, {"apiKeys.keyHash": hashed}]})
            if user:
                # B2B Audit: Update last_used
                if user.api_keys:
                    try:
                        for k in user.api_keys:
                            if k.key_hash == hashed:
                                k.last_used = datetime.utcnow()
                                await user.save()
                                break
                    except Exception:
                        pass
                return user
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
                user = await User.get(user_id)
                if user:
                    return user
        
        if api_key:
            hashed = hash_key(api_key)
            user = await User.find_one({"$or": [{"apiKeyHash": hashed}, {"apiKeys.keyHash": hashed}]})
            return user
    except Exception:
        pass
        
    return None
