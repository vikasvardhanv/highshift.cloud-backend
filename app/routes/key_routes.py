from fastapi import APIRouter, Depends, HTTPException, Body
from app.models.user import User, ApiKey
from app.utils.auth import get_current_user, hash_key
import secrets
import uuid

# Check if DB is ready
async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/keys", tags=["API Keys"], dependencies=[Depends(ensure_db)])

@router.get("")
async def get_keys(user: User = Depends(get_current_user)):
    return {"keys": user.api_keys}

@router.post("")
async def create_key(
    payload: dict = Body(...),
    user: User = Depends(get_current_user)
):
    name = payload.get("name", "New API Key")
    
    # 1. B2B / Scaling Limits
    # Limit number of API keys per user to prevent abuse
    MAX_KEYS = 10 
    if user.api_keys and len(user.api_keys) >= MAX_KEYS:
        raise HTTPException(status_code=400, detail=f"Maximum of {MAX_KEYS} API Keys allowed.")
    
    # Generate new key
    raw_key = f"hs_{secrets.token_hex(16)}"
    hashed = hash_key(raw_key)
    
    new_key = ApiKey(
        id=str(uuid.uuid4()),
        name=name,
        keyHash=hashed
    )
    
    if user.api_keys is None:
        user.api_keys = []
        
    user.api_keys.append(new_key)
    await user.save()
    
    # Return the raw key ONLY once
    return {"key": new_key, "rawApiKey": raw_key}

@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    user: User = Depends(get_current_user)
):
    original_count = len(user.api_keys)
    user.api_keys = [k for k in user.api_keys if k.id != key_id]
    
    if len(user.api_keys) == original_count:
        raise HTTPException(status_code=404, detail="Key not found")
        
    await user.save()
    return {"success": True, "remaining": len(user.api_keys)}
