import hashlib
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from app.models.user import User

API_KEY_NAME = "x-api-key"
api_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def hash_key(key: str) -> str:
    """Hash the API key (matching Node.js logic if possible)."""
    return hashlib.sha256(key.encode()).hexdigest()

async def get_current_user(api_key: str = Security(api_header)):
    """
    FastAPI dependency to validate API key and return the User.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key missing"
        )
    
    hashed = hash_key(api_key)
    user = await User.find_one({"apiKeyHash": hashed})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    
    return user
