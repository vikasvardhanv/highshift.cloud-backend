from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.utils.auth import get_current_user
from typing import List

async def ensure_db():
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()

router = APIRouter(prefix="/linked-accounts", tags=["Accounts"], dependencies=[Depends(ensure_db)])

@router.get("")
async def get_linked_accounts(user: User = Depends(get_current_user)):
    return {"accounts": user.linked_accounts}

@router.delete("/disconnect/{platform}/{account_id}")
async def disconnect_account(
    platform: str,
    account_id: str,
    user: User = Depends(get_current_user)
):
    # Filter out the account to remove
    original_count = len(user.linked_accounts)
    user.linked_accounts = [
        acc for acc in user.linked_accounts 
        if not (acc.platform == platform and acc.account_id == account_id)
    ]
    
    # If no change, maybe it didn't exist, but we can just return success or 404
    # For idempotency, success is fine, but if user wants to know if it worked:
    if len(user.linked_accounts) == original_count:
        raise HTTPException(status_code=404, detail="Account not found")
        
    await user.save()
    return {"message": "Disconnected successfully", "remaining": len(user.linked_accounts)}
