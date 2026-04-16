from fastapi import APIRouter, Depends, HTTPException, Body
from app.utils.auth import get_current_user, AuthUser, hash_key
from app.db.postgres import fetch_user_by_id, update_user
import secrets
import uuid
import json

router = APIRouter(prefix="/keys", tags=["API Keys"])

@router.get("")
async def get_keys(user: AuthUser = Depends(get_current_user)):
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"keys": user_row.get("api_keys") or []}

@router.post("")
async def create_key(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    name = payload.get("name", "New API Key")
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    api_keys = user_row.get("api_keys") or []
    
    # Limit number of API keys
    MAX_KEYS = 10 
    if len(api_keys) >= MAX_KEYS:
        raise HTTPException(status_code=400, detail=f"Maximum of {MAX_KEYS} API Keys allowed.")
    
    # Generate new key
    raw_key = f"hs_{secrets.token_hex(16)}"
    hashed = hash_key(raw_key)
    
    new_key = {
        "id": str(uuid.uuid4()),
        "name": name,
        "keyHash": hashed,
        "created_at": "2024-01-01T00:00:00",
        "lastUsed": None
    }
    
    api_keys.append(new_key)
    await update_user(user.id, {"api_keys": api_keys})
    
    # Return the raw key ONLY once
    return {"key": new_key, "rawApiKey": raw_key}

@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    user: AuthUser = Depends(get_current_user)
):
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    
    api_keys = user_row.get("api_keys") or []
    original_count = len(api_keys)
    api_keys = [k for k in api_keys if k.get("id") != key_id]
    
    if len(api_keys) == original_count:
        raise HTTPException(status_code=404, detail="Key not found")
    
    await update_user(user.id, {"api_keys": api_keys})
    return {"success": True, "remaining": len(api_keys)}

@router.get("/developer")
async def get_developer_keys(user: AuthUser = Depends(get_current_user)):
    user_row = await fetch_user_by_id(user.id)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"developer_keys": user_row.get("developer_keys") or {}}

@router.post("/developer")
async def update_developer_keys(
    payload: dict = Body(...),
    user: AuthUser = Depends(get_current_user)
):
    await update_user(user.id, {"developer_keys": payload})
    return {"success": True, "developer_keys": payload}
