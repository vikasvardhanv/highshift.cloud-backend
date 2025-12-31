from fastapi import APIRouter, Depends, HTTPException
import uuid
import hashlib
from app.utils.auth import get_current_user, hash_key
from app.models.user import User

router = APIRouter(prefix="/key", tags=["Security"])

@router.get("/me")
async def get_my_key_info(user: User = Depends(get_current_user)):
    return {
        "userId": str(user.id),
        "createdAt": user.created_at,
        "accountCount": len(user.linked_accounts)
    }

@router.post("/regenerate")
async def regenerate_api_key(userId: str):
    """
    Generate a new API key for a user.
    Note: For simplicity, this takes a userId. In a real app, this would be protected by 
    a session or a different auth mechanism.
    """
    user = await User.get(userId)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    new_key = f"hs_{uuid.uuid4().hex}"
    user.api_key_hash = hash_key(new_key)
    await user.save()
    
    return {
        "apiKey": new_key,
        "message": "Copy this key now. It will not be shown again."
    }
